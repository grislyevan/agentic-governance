"""Data-driven policy rule evaluator.

Loads rules as dicts (same schema as api/core/baseline_policies.py),
sorts by precedence (lower = higher priority), evaluates each rule's
conditions against detection context, returns first match.

This module is the internal engine behind ``evaluate_policy()`` in
``collector/engine/policy.py``.  It is not intended to be called
directly by external code.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.policy import NetworkContext, PolicyDecision, RULE_VERSION

logger = logging.getLogger(__name__)

# Severity ordering shared with policy.py
_SEVERITY_ORDER = {"detect": 0, "warn": 1, "approval_required": 2, "block": 3}

# Mapping helpers for numeric comparisons
_TIER_MAP = {"Tier0": 0, "Tier1": 1, "Tier2": 2, "Tier3": 3}
_RISK_MAP = {"R1": 1, "R2": 2, "R3": 3, "R4": 4}


@dataclass
class PolicyContext:
    """Bundles all evaluation inputs for the policy engine."""

    confidence: float
    confidence_class: str  # "High", "Medium", "Low"
    tool_class: str  # "A", "B", "C", "D"
    sensitivity: str  # "Tier0", "Tier1", "Tier2", "Tier3"
    action_risk: str  # "R1", "R2", "R3", "R4"
    explicit_deny: bool = False
    is_containerized: bool | None = None
    network_context: NetworkContext | None = None
    prior_violations: int = 0
    actor_trust_tier: str = "T1"


class PolicyEngine:
    """Data-driven policy rule evaluator.

    Loads rules as dicts, sorts by precedence (lower = higher priority),
    evaluates each rule's conditions against detection context, returns
    first match.
    """

    def __init__(self, rules: list[dict]) -> None:
        # Separate base rules from overlay rules
        self._base_rules: list[dict] = []
        self._overlay_rules: list[dict] = []

        for rule in rules:
            if not rule.get("is_active", True):
                continue
            # Detect overlay rules: either has overlay flag or category == "overlay"
            is_overlay = (
                rule.get("category") == "overlay"
                or rule.get("is_overlay", False)
            )
            if is_overlay:
                self._overlay_rules.append(rule)
            else:
                self._base_rules.append(rule)

        # Sort by precedence ascending (lower = higher priority, evaluated first)
        self._base_rules.sort(key=lambda r: r.get("precedence", 999))
        self._overlay_rules.sort(key=lambda r: r.get("precedence", 999))

    @property
    def base_rules(self) -> list[dict]:
        """Read-only access to the loaded base rules (sorted by precedence)."""
        return list(self._base_rules)

    @property
    def overlay_rules(self) -> list[dict]:
        """Read-only access to the loaded overlay rules (sorted by precedence)."""
        return list(self._overlay_rules)

    def evaluate(self, context: PolicyContext) -> PolicyDecision | None:
        """Evaluate base rules against context, return first match or None.

        Context-level reason codes (tool class, confidence, sensitivity,
        action risk) are prepended to every result for auditability.
        """
        context_reason_codes = _build_context_reason_codes(context)

        for rule in self._base_rules:
            if _matches(rule, context):
                reason_codes = list(context_reason_codes)
                reason_codes.extend(rule.get("reason_codes", []))
                return PolicyDecision(
                    decision_state=rule["decision_state"],
                    rule_id=rule["rule_id"],
                    rule_version=rule.get("rule_version", RULE_VERSION),
                    reason_codes=reason_codes,
                    decision_confidence=context.confidence,
                )

        return None

    def evaluate_overlays(
        self,
        context: PolicyContext,
        base_decision: PolicyDecision,
    ) -> PolicyDecision:
        """Evaluate overlay rules (network, container).

        Overlays can only ESCALATE, never downgrade the base decision.
        """
        result = base_decision

        # Network overlays
        if context.network_context is not None and context.network_context.unknown_connections > 0:
            net_decision = self._evaluate_network_overlay(context)
            if net_decision is not None:
                result = _higher_severity(result, net_decision)

        # Container isolation overlay
        if context.is_containerized is not None:
            iso_decision = self._evaluate_container_overlay(context)
            if iso_decision is not None:
                result = _higher_severity(result, iso_decision)

        return result

    def _evaluate_network_overlay(self, context: PolicyContext) -> PolicyDecision | None:
        """Evaluate network overlay rules against context."""
        if context.network_context is None or context.network_context.unknown_connections == 0:
            return None

        net_ctx = context.network_context
        base_reason_codes = [
            f"class_{context.tool_class.lower()}_tool",
            f"unknown_outbound_connections_{net_ctx.unknown_connections}",
        ]
        for dest in net_ctx.unknown_destinations[:5]:
            base_reason_codes.append(f"unknown_dest_{dest}")

        for rule in self._overlay_rules:
            conditions = rule.get("conditions", {})
            # Skip non-network rules
            if "unknown_outbound_min" not in conditions:
                continue
            if not _matches_overlay_network(rule, context):
                continue

            reason_codes = list(base_reason_codes)
            reason_codes.extend(rule.get("reason_codes", []))
            return PolicyDecision(
                decision_state=rule["decision_state"],
                rule_id=rule["rule_id"],
                rule_version=rule.get("rule_version", RULE_VERSION),
                reason_codes=reason_codes,
                decision_confidence=context.confidence,
            )

        return None

    def _evaluate_container_overlay(self, context: PolicyContext) -> PolicyDecision | None:
        """Evaluate container isolation overlay rules."""
        if context.tool_class not in ("C", "D"):
            return None
        if context.is_containerized:
            return None

        for rule in self._overlay_rules:
            conditions = rule.get("conditions", {})
            if not conditions.get("requires_container", False):
                continue
            tool_classes = conditions.get("tool_classes")
            if tool_classes and context.tool_class not in tool_classes:
                continue

            reason_codes = [
                f"class_c_tool_",  # matches original: tool_name is "" in evaluate_policy
            ]
            reason_codes.extend(rule.get("reason_codes", []))
            return PolicyDecision(
                decision_state=rule["decision_state"],
                rule_id=rule["rule_id"],
                rule_version=rule.get("rule_version", RULE_VERSION),
                reason_codes=reason_codes,
                decision_confidence=context.confidence,
            )

        return None


def _build_context_reason_codes(context: PolicyContext) -> list[str]:
    """Build the standard context-level reason codes prepended to every decision."""
    return [
        f"class_{context.tool_class.lower()}_tool",
        f"{context.confidence_class.lower()}_confidence",
        f"sensitivity_{context.sensitivity.lower()}",
        f"action_risk_{context.action_risk.lower()}",
    ]


def _matches(rule: dict, context: PolicyContext) -> bool:
    """Check if all conditions in a rule match the given context.

    Unspecified conditions are treated as 'any' (always match).
    All specified conditions must match (AND logic).
    """
    conditions = rule.get("conditions", {})

    # confidence_band: list of allowed confidence classes
    if "confidence_band" in conditions:
        if context.confidence_class not in conditions["confidence_band"]:
            return False

    # tool_classes: list of allowed tool classes
    if "tool_classes" in conditions:
        if context.tool_class not in conditions["tool_classes"]:
            return False

    # sensitivity_tiers: explicit list of allowed tiers
    if "sensitivity_tiers" in conditions:
        if context.sensitivity not in conditions["sensitivity_tiers"]:
            return False

    # sensitivity_tier_min: minimum tier (>=)
    if "sensitivity_tier_min" in conditions:
        tier_num = _TIER_MAP.get(context.sensitivity, 0)
        min_num = _TIER_MAP.get(conditions["sensitivity_tier_min"], 0)
        if tier_num < min_num:
            return False

    # sensitivity_tier_max: maximum tier (<=)
    if "sensitivity_tier_max" in conditions:
        tier_num = _TIER_MAP.get(context.sensitivity, 0)
        max_num = _TIER_MAP.get(conditions["sensitivity_tier_max"], 0)
        if tier_num > max_num:
            return False

    # action_risk_min: minimum risk level (>=)
    if "action_risk_min" in conditions:
        risk_num = _RISK_MAP.get(context.action_risk, 1)
        min_num = _RISK_MAP.get(conditions["action_risk_min"], 1)
        if risk_num < min_num:
            return False

    # action_risk_max: maximum risk level (<=)
    if "action_risk_max" in conditions:
        risk_num = _RISK_MAP.get(context.action_risk, 1)
        max_num = _RISK_MAP.get(conditions["action_risk_max"], 1)
        if risk_num > max_num:
            return False

    # explicit_deny: must match exactly
    if "explicit_deny" in conditions:
        if conditions["explicit_deny"] != context.explicit_deny:
            return False

    return True


def _matches_overlay_network(rule: dict, context: PolicyContext) -> bool:
    """Check if a network overlay rule matches."""
    conditions = rule.get("conditions", {})

    if "tool_classes" in conditions:
        if context.tool_class not in conditions["tool_classes"]:
            return False

    if "unknown_outbound_min" in conditions:
        if context.network_context is None:
            return False
        if context.network_context.unknown_connections < conditions["unknown_outbound_min"]:
            return False

    return True


def _higher_severity(a: PolicyDecision, b: PolicyDecision) -> PolicyDecision:
    """Return whichever decision is more severe, merging reason codes.

    Mirrors the logic in policy._higher_severity exactly.
    """
    a_sev = _SEVERITY_ORDER.get(a.decision_state, 0)
    b_sev = _SEVERITY_ORDER.get(b.decision_state, 0)
    if b_sev > a_sev:
        b.reason_codes = list(dict.fromkeys(a.reason_codes + b.reason_codes))
        return b
    if b_sev == a_sev:
        a.reason_codes = list(dict.fromkeys(a.reason_codes + b.reason_codes))
    return a


def load_rules_from_file(path: Path) -> dict[str, list[dict]]:
    """Load policy rules from a JSON file.

    Returns a dict with keys 'rules' (base rules) and 'overlay_rules'.
    Returns empty lists if the file is missing or invalid.
    """
    if not path.exists():
        logger.warning("Policy rules file not found: %s", path)
        return {"rules": [], "overlay_rules": []}

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("Policy rules file %s does not contain a JSON object", path)
            return {"rules": [], "overlay_rules": []}
        rules = data.get("rules", [])
        overlay_rules = data.get("overlay_rules", [])
        if not isinstance(rules, list):
            rules = []
        if not isinstance(overlay_rules, list):
            overlay_rules = []
        return {"rules": rules, "overlay_rules": overlay_rules}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read policy rules from %s: %s", path, exc)
        return {"rules": [], "overlay_rules": []}


def create_engine_from_file(path: Path) -> PolicyEngine:
    """Create a PolicyEngine instance from a JSON rules file."""
    data = load_rules_from_file(path)
    all_rules = data["rules"] + data["overlay_rules"]
    return PolicyEngine(all_rules)
