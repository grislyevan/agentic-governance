"""Policy evaluation engine implementing Playbook Section 6.3 deterministic escalation rules."""

from __future__ import annotations

from dataclasses import dataclass

RULE_VERSION = "0.1.0"


@dataclass
class PolicyDecision:
    """Result of policy evaluation."""

    decision_state: str  # detect | warn | approval_required | block
    rule_id: str
    rule_version: str
    reason_codes: list[str]
    decision_confidence: float


def evaluate_policy(
    confidence: float,
    confidence_class: str,
    tool_class: str,
    sensitivity: str,
    action_risk: str,
    explicit_deny: bool = False,
) -> PolicyDecision:
    """Evaluate deterministic escalation rules from Playbook Section 6.3.

    Returns the highest-severity matching rule.
    """
    tier_num = _tier_to_int(sensitivity)
    risk_num = _risk_to_int(action_risk)
    reason_codes: list[str] = []

    reason_codes.append(f"class_{tool_class.lower()}_tool")
    reason_codes.append(f"{confidence_class.lower()}_confidence")
    reason_codes.append(f"sensitivity_{sensitivity.lower()}")
    reason_codes.append(f"action_risk_{action_risk.lower()}")

    # Rule 5: Any confidence + explicit deny + Tier 3 → Block (highest priority)
    if explicit_deny and tier_num >= 3:
        reason_codes.append("explicit_deny_tier3")
        return PolicyDecision(
            decision_state="block",
            rule_id="ENFORCE-005",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Rule 4: High confidence + disallowed R4 → Block
    if confidence_class == "High" and risk_num >= 4:
        reason_codes.append("high_confidence_disallowed_r4")
        return PolicyDecision(
            decision_state="block",
            rule_id="ENFORCE-004",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Rule 6: Class C + medium+ confidence + R3 → Approval Required
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

    # Rule 3: Medium confidence + Tier 2/3 + R3 → Approval Required
    if confidence_class == "Medium" and tier_num >= 2 and risk_num >= 3:
        reason_codes.append("medium_confidence_sensitive_scope")
        return PolicyDecision(
            decision_state="approval_required",
            rule_id="ENFORCE-003",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Rule 2: Medium confidence + Tier 1/2 + R2 → Warn
    if confidence_class == "Medium" and tier_num >= 1 and risk_num >= 2:
        reason_codes.append("medium_confidence_scoped_write")
        return PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-002",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Rule 1: Low confidence + Tier 0/1 + R1 → Detect
    if confidence_class == "Low" and tier_num <= 1 and risk_num <= 1:
        reason_codes.append("low_confidence_low_risk")
        return PolicyDecision(
            decision_state="detect",
            rule_id="ENFORCE-001",
            rule_version=RULE_VERSION,
            reason_codes=reason_codes,
            decision_confidence=confidence,
        )

    # Fallbacks: no numbered rule matched exactly — apply best-fit by confidence class.
    # This happens when the tier/risk combination doesn't align with a specific rule
    # (e.g., Medium confidence at Tier0 with R2 doesn't match Rule 2's Tier1+ requirement).
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
