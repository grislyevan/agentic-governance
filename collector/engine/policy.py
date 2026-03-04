"""Policy evaluation engine implementing Playbook Section 6.3 deterministic escalation rules.

Class D rules (ENFORCE-D01 through ENFORCE-D03) take precedence over general rules 1–7
and reflect the stricter governance posture required for Persistent Autonomous Agents.

Network rules (NET-001 through NET-003) correlate active tool connections with an
allowlist to detect data exfiltration risk.

Container isolation rule (ISO-001) requires Class C agents to run inside containers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RULE_VERSION = "0.2.0"


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    decision_state: str  # detect | warn | approval_required | block
    rule_id: str
    rule_version: str
    reason_codes: list[str]
    decision_confidence: float


@dataclass
class NetworkContext:
    """Enrichment from the network correlation engine."""

    unknown_connections: int = 0
    unknown_destinations: list[str] = field(default_factory=list)
    total_connections: int = 0


def evaluate_network_policy(
    tool_class: str,
    tool_name: str,
    confidence: float,
    net_ctx: NetworkContext,
) -> PolicyDecision | None:
    """Evaluate network-specific policy rules.

    Returns a PolicyDecision if a network rule triggers, None otherwise.
    The caller should use the higher-severity decision between this and
    the standard evaluate_policy() result.
    """
    if net_ctx.unknown_connections == 0:
        return None

    reason_codes = [
        f"class_{tool_class.lower()}_tool",
        f"unknown_outbound_connections_{net_ctx.unknown_connections}",
    ]
    for dest in net_ctx.unknown_destinations[:5]:
        reason_codes.append(f"unknown_dest_{dest}")

    # NET-003: Any tool + known-malicious destination → block
    # (Placeholder — requires threat-intel feed integration)

    # NET-002: Class C/D + unknown outbound + high volume → block (exfiltration risk)
    if tool_class in ("C", "D") and net_ctx.unknown_connections >= 3:
        reason_codes.append("high_volume_unknown_outbound_exfiltration_risk")
        return PolicyDecision(
            decision_state="block",
            rule_id="NET-002",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # NET-001: Class C + unknown outbound → approval_required
    if tool_class in ("C", "D"):
        reason_codes.append("autonomous_tool_unknown_outbound")
        return PolicyDecision(
            decision_state="approval_required",
            rule_id="NET-001",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    return None


def evaluate_container_policy(
    tool_class: str,
    tool_name: str,
    confidence: float,
    is_containerized: bool,
) -> PolicyDecision | None:
    """ISO-001: Class C agents must run inside a container."""
    if tool_class != "C":
        return None
    if is_containerized:
        return None

    return PolicyDecision(
        decision_state="block",
        rule_id="ISO-001",
        rule_version=RULE_VERSION,
        reason_codes=[
            f"class_c_tool_{tool_name.lower().replace(' ', '_')}",
            "container_isolation_required",
            "process_not_child_of_docker",
        ],
        decision_confidence=confidence,
    )


def evaluate_policy(
    confidence: float,
    confidence_class: str,
    tool_class: str,
    sensitivity: str,
    action_risk: str,
    explicit_deny: bool = False,
    net_ctx: NetworkContext | None = None,
    is_containerized: bool | None = None,
) -> PolicyDecision:
    """Evaluate deterministic escalation rules from Playbook Section 6.3.

    Returns the highest-severity matching rule.  Network and container
    rules are evaluated as overlays — they can only *escalate*, never
    downgrade the base decision.
    """
    base = _evaluate_base_rules(
        confidence, confidence_class, tool_class, sensitivity,
        action_risk, explicit_deny,
    )

    # Network overlay: escalate if connections to unknown destinations
    if net_ctx is not None:
        net_decision = evaluate_network_policy(
            tool_class, "", confidence, net_ctx,
        )
        if net_decision is not None:
            base = _higher_severity(base, net_decision)

    # Container isolation overlay
    if is_containerized is not None:
        iso_decision = evaluate_container_policy(
            tool_class, "", confidence, is_containerized,
        )
        if iso_decision is not None:
            base = _higher_severity(base, iso_decision)

    return base


_SEVERITY_ORDER = {"detect": 0, "warn": 1, "approval_required": 2, "block": 3}


def _higher_severity(a: PolicyDecision, b: PolicyDecision) -> PolicyDecision:
    """Return whichever decision is more severe, merging reason codes."""
    a_sev = _SEVERITY_ORDER.get(a.decision_state, 0)
    b_sev = _SEVERITY_ORDER.get(b.decision_state, 0)
    if b_sev > a_sev:
        b.reason_codes = list(dict.fromkeys(a.reason_codes + b.reason_codes))
        return b
    if b_sev == a_sev:
        a.reason_codes = list(dict.fromkeys(a.reason_codes + b.reason_codes))
    return a


def _evaluate_base_rules(
    confidence: float,
    confidence_class: str,
    tool_class: str,
    sensitivity: str,
    action_risk: str,
    explicit_deny: bool,
) -> PolicyDecision:
    """Core deterministic escalation rules (unchanged from Playbook v0.3)."""
    tier_num = _tier_to_int(sensitivity)
    risk_num = _risk_to_int(action_risk)
    reason_codes: list[str] = []

    reason_codes.append(f"class_{tool_class.lower()}_tool")
    reason_codes.append(f"{confidence_class.lower()}_confidence")
    reason_codes.append(f"sensitivity_{sensitivity.lower()}")
    reason_codes.append(f"action_risk_{action_risk.lower()}")

    # --- Class D rules (take precedence over general rules) ---

    if tool_class == "D" and risk_num >= 3:
        reason_codes.append("class_d_persistent_autonomous_agent")
        reason_codes.append("r3_or_higher_action_always_block_for_class_d")
        return PolicyDecision(
            decision_state="block",
            rule_id="ENFORCE-D01",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if tool_class == "D" and confidence_class in ("Medium", "High") and risk_num >= 2:
        reason_codes.append("class_d_persistent_autonomous_agent")
        reason_codes.append("medium_or_high_confidence_write_requires_approval")
        return PolicyDecision(
            decision_state="approval_required",
            rule_id="ENFORCE-D02",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if tool_class == "D":
        reason_codes.append("class_d_persistent_autonomous_agent")
        reason_codes.append("always_on_agent_no_safe_baseline")
        return PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-D03",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # --- General rules (Class A / B / C) ---

    if explicit_deny and tier_num >= 3:
        reason_codes.append("explicit_deny_tier3")
        return PolicyDecision(
            decision_state="block",
            rule_id="ENFORCE-005",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if confidence_class == "High" and risk_num >= 4:
        reason_codes.append("high_confidence_disallowed_r4")
        return PolicyDecision(
            decision_state="block",
            rule_id="ENFORCE-004",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if tool_class == "C" and confidence_class in ("Medium", "High") and risk_num >= 3:
        reason_codes.append("class_c_autonomous_executor")
        reason_codes.append("medium_or_high_confidence_r3")
        return PolicyDecision(
            decision_state="approval_required",
            rule_id="ENFORCE-006",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if confidence_class == "Medium" and tier_num >= 2 and risk_num >= 3:
        reason_codes.append("medium_confidence_sensitive_scope")
        return PolicyDecision(
            decision_state="approval_required",
            rule_id="ENFORCE-003",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if confidence_class == "Medium" and tier_num >= 1 and risk_num >= 2:
        reason_codes.append("medium_confidence_scoped_write")
        return PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-002",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if confidence_class == "Low" and tier_num <= 1 and risk_num <= 1:
        reason_codes.append("low_confidence_low_risk")
        return PolicyDecision(
            decision_state="detect",
            rule_id="ENFORCE-001",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Fallbacks
    if confidence_class == "High":
        if risk_num >= 3:
            reason_codes.append("fallback_high_confidence_broad_action")
            return PolicyDecision(
                decision_state="approval_required",
                rule_id="ENFORCE-003-F",
                rule_version=RULE_VERSION,
                reason_codes=reason_codes,
                decision_confidence=confidence,
            )
        reason_codes.append("fallback_high_confidence_detected")
        return PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-002-F",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    if confidence_class == "Medium":
        reason_codes.append("fallback_medium_confidence_no_rule_match")
        return PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-002-F",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    reason_codes.append("fallback_low_confidence_default")
    return PolicyDecision(
        decision_state="detect",
        rule_id="ENFORCE-001-F",
        rule_version=RULE_VERSION,
        reason_codes=reason_codes,
        decision_confidence=confidence,
    )


def _tier_to_int(tier: str) -> int:
    return {"Tier0": 0, "Tier1": 1, "Tier2": 2, "Tier3": 3}.get(tier, 0)


def _risk_to_int(risk: str) -> int:
    return {"R1": 1, "R2": 2, "R3": 3, "R4": 4}.get(risk, 1)
