"""Tests for collector/engine/policy.py: evaluate_policy and PolicyDecision."""

import unittest

from engine.policy import RULE_VERSION, PolicyDecision, evaluate_policy


class TestEvaluatePolicy(unittest.TestCase):
    """Test deterministic escalation rules (Playbook Section 6.3)."""

    def test_rule_5_explicit_deny_tier3_blocks(self):
        decision = evaluate_policy(
            confidence=0.9,
            confidence_class="High",
            tool_class="C",
            sensitivity="Tier3",
            action_risk="R2",
            explicit_deny=True,
        )
        self.assertEqual(decision.decision_state, "block")
        self.assertEqual(decision.rule_id, "ENFORCE-005")
        self.assertEqual(decision.rule_version, RULE_VERSION)
        self.assertIn("explicit_deny_tier3", decision.reason_codes)

    def test_rule_4_high_confidence_r4_blocks(self):
        decision = evaluate_policy(
            confidence=0.8,
            confidence_class="High",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R4",
        )
        self.assertEqual(decision.decision_state, "block")
        self.assertEqual(decision.rule_id, "ENFORCE-004")
        self.assertIn("high_confidence_disallowed_r4", decision.reason_codes)

    def test_rule_6_class_c_medium_high_r3_approval_required(self):
        decision = evaluate_policy(
            confidence=0.6,
            confidence_class="Medium",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R3",
        )
        self.assertEqual(decision.decision_state, "approval_required")
        self.assertEqual(decision.rule_id, "ENFORCE-006")
        self.assertIn("class_c_autonomous_executor", decision.reason_codes)

    def test_rule_3_medium_confidence_tier2_r3_approval_required(self):
        decision = evaluate_policy(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="B",
            sensitivity="Tier2",
            action_risk="R3",
        )
        self.assertEqual(decision.decision_state, "approval_required")
        self.assertEqual(decision.rule_id, "ENFORCE-003")

    def test_rule_2_medium_confidence_tier1_r2_warn(self):
        decision = evaluate_policy(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="A",
            sensitivity="Tier1",
            action_risk="R2",
        )
        self.assertEqual(decision.decision_state, "warn")
        self.assertEqual(decision.rule_id, "ENFORCE-002")

    def test_rule_1_low_confidence_tier0_r1_detect(self):
        decision = evaluate_policy(
            confidence=0.3,
            confidence_class="Low",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R1",
        )
        self.assertEqual(decision.decision_state, "detect")
        self.assertEqual(decision.rule_id, "ENFORCE-001")
        self.assertIn("low_confidence_low_risk", decision.reason_codes)

    def test_fallback_high_confidence_r3_approval_required(self):
        decision = evaluate_policy(
            confidence=0.8,
            confidence_class="High",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R3",
        )
        self.assertEqual(decision.decision_state, "approval_required")
        self.assertEqual(decision.rule_id, "ENFORCE-003-F")

    def test_fallback_high_confidence_r2_warn(self):
        decision = evaluate_policy(
            confidence=0.8,
            confidence_class="High",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R2",
        )
        self.assertEqual(decision.decision_state, "warn")
        self.assertEqual(decision.rule_id, "ENFORCE-002-F")

    def test_fallback_medium_confidence_warn(self):
        decision = evaluate_policy(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R1",
        )
        self.assertEqual(decision.decision_state, "warn")
        self.assertEqual(decision.rule_id, "ENFORCE-002-F")

    def test_fallback_low_confidence_detect(self):
        decision = evaluate_policy(
            confidence=0.2,
            confidence_class="Low",
            tool_class="B",
            sensitivity="Tier2",
            action_risk="R3",
        )
        self.assertEqual(decision.decision_state, "detect")
        self.assertEqual(decision.rule_id, "ENFORCE-001-F")

    def test_decision_confidence_preserved(self):
        decision = evaluate_policy(
            confidence=0.77,
            confidence_class="High",
            tool_class="C",
            sensitivity="Tier0",
            action_risk="R2",
        )
        self.assertEqual(decision.decision_confidence, 0.77)

    def test_reason_codes_include_context(self):
        decision = evaluate_policy(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R2",
        )
        self.assertIn("class_c_tool", decision.reason_codes)
        self.assertIn("medium_confidence", decision.reason_codes)
        self.assertIn("sensitivity_tier1", decision.reason_codes)
        self.assertIn("action_risk_r2", decision.reason_codes)


if __name__ == "__main__":
    unittest.main()
