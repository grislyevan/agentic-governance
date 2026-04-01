"""Tests for the data-driven PolicyEngine (collector/engine/policy_engine.py).

These tests verify that the data-driven engine produces identical results
to the hardcoded ``_evaluate_base_rules`` for all tested scenarios, and
that custom rule overrides, precedence ordering, and overlay semantics
work correctly.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from engine.policy import (
    RULE_VERSION,
    PolicyDecision,
    evaluate_policy,
    _evaluate_base_rules,
    _tier_to_int,
    _risk_to_int,
)
from engine.policy_engine import (
    PolicyContext,
    PolicyEngine,
    _build_context_reason_codes,
    _matches,
    create_engine_from_file,
    load_rules_from_file,
)


# Path to the baseline rules JSON shipped with the collector
_POLICIES_JSON = Path(__file__).resolve().parent.parent / "config" / "policies.json"


class TestPolicyEngineLoadsFromFile(unittest.TestCase):
    """Verify that rules can be loaded from the JSON file."""

    def test_rules_loaded_from_json_file(self):
        """policies.json exists and loads into a valid PolicyEngine."""
        self.assertTrue(_POLICIES_JSON.exists(), f"Missing {_POLICIES_JSON}")
        engine = create_engine_from_file(_POLICIES_JSON)
        self.assertIsNotNone(engine)
        # Should have base rules and overlay rules
        self.assertGreater(len(engine.base_rules), 0)
        # Overlays are loaded into overlay_rules
        self.assertGreater(len(engine.overlay_rules), 0)

    def test_rules_loaded_from_nonexistent_file(self):
        """A missing file should produce an engine with no rules."""
        engine = create_engine_from_file(Path("/nonexistent/policies.json"))
        self.assertEqual(len(engine.base_rules), 0)
        self.assertEqual(len(engine.overlay_rules), 0)

    def test_load_rules_from_file_returns_structure(self):
        """load_rules_from_file returns dict with 'rules' and 'overlay_rules' keys."""
        data = load_rules_from_file(_POLICIES_JSON)
        self.assertIn("rules", data)
        self.assertIn("overlay_rules", data)
        self.assertIsInstance(data["rules"], list)
        self.assertIsInstance(data["overlay_rules"], list)

    def test_load_from_temp_file(self):
        """Rules can be loaded from a custom path."""
        rules_data = {
            "rules": [
                {
                    "rule_id": "CUSTOM-001",
                    "rule_version": "1.0.0",
                    "decision_state": "warn",
                    "conditions": {"confidence_band": ["High"]},
                    "reason_codes": ["custom_rule"],
                    "precedence": 100,
                    "is_active": True,
                }
            ],
            "overlay_rules": [],
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump(rules_data, fh)
            tmp_path = Path(fh.name)
        try:
            engine = create_engine_from_file(tmp_path)
            self.assertEqual(len(engine.base_rules), 1)
            self.assertEqual(engine.base_rules[0]["rule_id"], "CUSTOM-001")
        finally:
            os.unlink(tmp_path)


class TestPolicyEngineEmptyRules(unittest.TestCase):
    """Edge case: engine with no rules."""

    def test_policy_engine_with_empty_rules_returns_none(self):
        engine = PolicyEngine([])
        ctx = PolicyContext(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="A",
            sensitivity="Tier1",
            action_risk="R2",
        )
        result = engine.evaluate(ctx)
        self.assertIsNone(result)


class TestRulePrecedenceOrdering(unittest.TestCase):
    """Verify that lower precedence number wins (evaluated first)."""

    def test_rule_precedence_ordering(self):
        """When two rules match the same context, the lower precedence wins."""
        rules = [
            {
                "rule_id": "LATE-RULE",
                "decision_state": "detect",
                "conditions": {"confidence_band": ["High"]},
                "reason_codes": ["late"],
                "precedence": 200,
                "is_active": True,
            },
            {
                "rule_id": "EARLY-RULE",
                "decision_state": "block",
                "conditions": {"confidence_band": ["High"]},
                "reason_codes": ["early"],
                "precedence": 100,
                "is_active": True,
            },
        ]
        engine = PolicyEngine(rules)
        ctx = PolicyContext(
            confidence=0.9,
            confidence_class="High",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R1",
        )
        decision = engine.evaluate(ctx)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.rule_id, "EARLY-RULE")
        self.assertEqual(decision.decision_state, "block")

    def test_precedence_sorts_ascending(self):
        """base_rules are sorted by precedence ascending after construction."""
        rules = [
            {"rule_id": "C", "precedence": 300, "decision_state": "detect",
             "conditions": {}, "reason_codes": [], "is_active": True},
            {"rule_id": "A", "precedence": 100, "decision_state": "detect",
             "conditions": {}, "reason_codes": [], "is_active": True},
            {"rule_id": "B", "precedence": 200, "decision_state": "detect",
             "conditions": {}, "reason_codes": [], "is_active": True},
        ]
        engine = PolicyEngine(rules)
        ids = [r["rule_id"] for r in engine.base_rules]
        self.assertEqual(ids, ["A", "B", "C"])


class TestCustomRuleOverrides(unittest.TestCase):
    """Custom rules can override baseline behavior."""

    def test_custom_rule_overrides_baseline(self):
        """A custom rule with same conditions but different decision wins when
        it has a lower precedence number."""
        custom_rules = [
            {
                "rule_id": "CUSTOM-BLOCK-LOW",
                "decision_state": "block",
                "conditions": {
                    "confidence_band": ["Low"],
                    "sensitivity_tier_max": "Tier1",
                    "action_risk_max": "R1",
                },
                "reason_codes": ["custom_block_override"],
                "precedence": 50,  # Lower than ENFORCE-001's 600
                "is_active": True,
            },
            # Include the fallback so engine doesn't return None
            {
                "rule_id": "ENFORCE-001-F",
                "decision_state": "detect",
                "conditions": {},
                "reason_codes": ["fallback_low_confidence_default"],
                "precedence": 900,
                "is_active": True,
                "is_fallback": True,
            },
        ]
        engine = PolicyEngine(custom_rules)
        ctx = PolicyContext(
            confidence=0.3,
            confidence_class="Low",
            tool_class="A",
            sensitivity="Tier0",
            action_risk="R1",
        )
        decision = engine.evaluate(ctx)
        self.assertIsNotNone(decision)
        self.assertEqual(decision.rule_id, "CUSTOM-BLOCK-LOW")
        self.assertEqual(decision.decision_state, "block")
        self.assertIn("custom_block_override", decision.reason_codes)

    def test_inactive_rule_is_skipped(self):
        """Rules with is_active=False are not loaded into the engine."""
        rules = [
            {
                "rule_id": "DISABLED",
                "decision_state": "block",
                "conditions": {},
                "reason_codes": ["disabled"],
                "precedence": 1,
                "is_active": False,
            },
            {
                "rule_id": "ACTIVE",
                "decision_state": "detect",
                "conditions": {},
                "reason_codes": ["active"],
                "precedence": 100,
                "is_active": True,
            },
        ]
        engine = PolicyEngine(rules)
        self.assertEqual(len(engine.base_rules), 1)
        self.assertEqual(engine.base_rules[0]["rule_id"], "ACTIVE")


class TestOverlayCanOnlyEscalate(unittest.TestCase):
    """Overlay rules (network, container) must not downgrade decisions."""

    def test_overlay_can_only_escalate(self):
        """An overlay with lower severity than the base decision does not downgrade."""
        from engine.policy import NetworkContext

        rules_data = load_rules_from_file(_POLICIES_JSON)
        all_rules = rules_data["rules"] + rules_data["overlay_rules"]
        engine = PolicyEngine(all_rules)

        # Base decision: block (from ENFORCE-D01: Class D + R3)
        ctx = PolicyContext(
            confidence=0.9,
            confidence_class="High",
            tool_class="D",
            sensitivity="Tier0",
            action_risk="R3",
        )
        base = engine.evaluate(ctx)
        self.assertIsNotNone(base)
        self.assertEqual(base.decision_state, "block")

        # Apply network overlay that would be approval_required (NET-001)
        ctx.network_context = NetworkContext(
            unknown_connections=1,
            unknown_destinations=["8.8.8.8"],
        )
        result = engine.evaluate_overlays(ctx, base)
        # Should stay at block, not downgrade to approval_required
        self.assertEqual(result.decision_state, "block")

    def test_overlay_escalates_from_detect_to_approval(self):
        """A network overlay can escalate a detect to approval_required."""
        from engine.policy import NetworkContext

        rules_data = load_rules_from_file(_POLICIES_JSON)
        all_rules = rules_data["rules"] + rules_data["overlay_rules"]
        engine = PolicyEngine(all_rules)

        # Base: warn for Class C + Medium + R2 (ENFORCE-002 range, but
        # we need Class C with net context. Let's use a detect-level base.)
        # Use: Low, C, Tier0, R1 -> ENFORCE-001 detect
        ctx = PolicyContext(
            confidence=0.3,
            confidence_class="Low",
            tool_class="C",
            sensitivity="Tier0",
            action_risk="R1",
            network_context=NetworkContext(
                unknown_connections=1,
                unknown_destinations=["10.0.0.1"],
            ),
        )
        base = engine.evaluate(ctx)
        self.assertIsNotNone(base)
        self.assertEqual(base.decision_state, "detect")

        result = engine.evaluate_overlays(ctx, base)
        # NET-001 should escalate to approval_required
        self.assertEqual(result.decision_state, "approval_required")


class TestBackwardCompatibleResults(unittest.TestCase):
    """Explicitly verify that data-driven engine matches hardcoded engine
    for a matrix of representative inputs.

    This is the core regression gate beyond the existing test_policy.py tests.
    """

    # Matrix of inputs covering every rule path
    _MATRIX = [
        # (confidence, confidence_class, tool_class, sensitivity, action_risk, explicit_deny)
        # Class D rules
        (0.9, "High", "D", "Tier0", "R3", False),   # D01
        (0.9, "High", "D", "Tier0", "R4", False),   # D01
        (0.5, "Medium", "D", "Tier1", "R2", False),  # D02
        (0.8, "High", "D", "Tier0", "R2", False),    # D02
        (0.3, "Low", "D", "Tier0", "R1", False),     # D03
        (0.5, "Medium", "D", "Tier0", "R1", False),  # D03 (medium, risk=1 -> no D02)
        # General rules
        (0.9, "High", "C", "Tier3", "R2", True),     # 005
        (0.3, "Low", "A", "Tier3", "R1", True),      # 005
        (0.8, "High", "B", "Tier0", "R4", False),    # 004
        (0.8, "High", "C", "Tier1", "R4", False),    # 004
        (0.6, "Medium", "C", "Tier1", "R3", False),  # 006
        (0.8, "High", "C", "Tier0", "R3", False),    # 006
        (0.5, "Medium", "B", "Tier2", "R3", False),  # 003
        (0.5, "Medium", "A", "Tier3", "R4", False),  # 003
        (0.5, "Medium", "A", "Tier1", "R2", False),  # 002
        (0.5, "Medium", "B", "Tier2", "R2", False),  # 002
        (0.3, "Low", "A", "Tier0", "R1", False),     # 001
        (0.3, "Low", "B", "Tier1", "R1", False),     # 001
        # Fallbacks
        (0.8, "High", "A", "Tier0", "R3", False),    # 003-F
        (0.8, "High", "B", "Tier0", "R4", False),    # 004 (not fallback)
        (0.8, "High", "A", "Tier0", "R2", False),    # 002-F (high)
        (0.8, "High", "A", "Tier0", "R1", False),    # 002-F (high)
        (0.5, "Medium", "A", "Tier0", "R1", False),  # 002-F (medium)
        (0.2, "Low", "B", "Tier2", "R3", False),     # 001-F
        (0.2, "Low", "C", "Tier3", "R4", False),     # 001-F
    ]

    def test_backward_compatible_results(self):
        """For each input in the matrix, the data-driven engine must produce
        the same rule_id, decision_state, and reason_codes as the hardcoded engine.
        """
        engine = create_engine_from_file(_POLICIES_JSON)
        self.assertIsNotNone(engine)

        for conf, conf_cls, tc, sens, risk, deny in self._MATRIX:
            with self.subTest(
                confidence=conf,
                confidence_class=conf_cls,
                tool_class=tc,
                sensitivity=sens,
                action_risk=risk,
                explicit_deny=deny,
            ):
                # Hardcoded result
                expected = _evaluate_base_rules(
                    conf, conf_cls, tc, sens, risk, deny,
                )

                # Data-driven result
                ctx = PolicyContext(
                    confidence=conf,
                    confidence_class=conf_cls,
                    tool_class=tc,
                    sensitivity=sens,
                    action_risk=risk,
                    explicit_deny=deny,
                )
                actual = engine.evaluate(ctx)

                self.assertIsNotNone(
                    actual,
                    f"Engine returned None for {conf_cls}/{tc}/{sens}/{risk}",
                )
                self.assertEqual(
                    actual.rule_id, expected.rule_id,
                    f"rule_id mismatch for {conf_cls}/{tc}/{sens}/{risk}",
                )
                self.assertEqual(
                    actual.decision_state, expected.decision_state,
                    f"decision_state mismatch for {conf_cls}/{tc}/{sens}/{risk}",
                )
                self.assertEqual(
                    actual.decision_confidence, expected.decision_confidence,
                )
                # Reason codes: same set in same order
                self.assertEqual(
                    actual.reason_codes, expected.reason_codes,
                    f"reason_codes mismatch for {conf_cls}/{tc}/{sens}/{risk}:\n"
                    f"  expected: {expected.reason_codes}\n"
                    f"  actual:   {actual.reason_codes}",
                )


class TestConditionMatching(unittest.TestCase):
    """Unit tests for individual condition matchers."""

    def test_confidence_band_matches(self):
        rule = {"conditions": {"confidence_band": ["Medium", "High"]}}
        ctx = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
        )
        self.assertTrue(_matches(rule, ctx))

    def test_confidence_band_does_not_match(self):
        rule = {"conditions": {"confidence_band": ["High"]}}
        ctx = PolicyContext(
            confidence=0.3, confidence_class="Low",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
        )
        self.assertFalse(_matches(rule, ctx))

    def test_tool_classes_match(self):
        rule = {"conditions": {"tool_classes": ["C", "D"]}}
        ctx = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="C", sensitivity="Tier0", action_risk="R1",
        )
        self.assertTrue(_matches(rule, ctx))

    def test_tool_classes_no_match(self):
        rule = {"conditions": {"tool_classes": ["C", "D"]}}
        ctx = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
        )
        self.assertFalse(_matches(rule, ctx))

    def test_sensitivity_tier_min(self):
        rule = {"conditions": {"sensitivity_tier_min": "Tier2"}}
        ctx_ok = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier3", action_risk="R1",
        )
        ctx_fail = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier1", action_risk="R1",
        )
        self.assertTrue(_matches(rule, ctx_ok))
        self.assertFalse(_matches(rule, ctx_fail))

    def test_sensitivity_tier_max(self):
        rule = {"conditions": {"sensitivity_tier_max": "Tier1"}}
        ctx_ok = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
        )
        ctx_fail = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier2", action_risk="R1",
        )
        self.assertTrue(_matches(rule, ctx_ok))
        self.assertFalse(_matches(rule, ctx_fail))

    def test_action_risk_min_and_max(self):
        rule = {"conditions": {"action_risk_min": "R2", "action_risk_max": "R3"}}
        for risk, expected in [("R1", False), ("R2", True), ("R3", True), ("R4", False)]:
            ctx = PolicyContext(
                confidence=0.5, confidence_class="Medium",
                tool_class="A", sensitivity="Tier0", action_risk=risk,
            )
            self.assertEqual(
                _matches(rule, ctx), expected,
                f"Expected {expected} for {risk}",
            )

    def test_explicit_deny_condition(self):
        rule = {"conditions": {"explicit_deny": True}}
        ctx_yes = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
            explicit_deny=True,
        )
        ctx_no = PolicyContext(
            confidence=0.5, confidence_class="Medium",
            tool_class="A", sensitivity="Tier0", action_risk="R1",
            explicit_deny=False,
        )
        self.assertTrue(_matches(rule, ctx_yes))
        self.assertFalse(_matches(rule, ctx_no))

    def test_empty_conditions_always_match(self):
        rule = {"conditions": {}}
        ctx = PolicyContext(
            confidence=0.1, confidence_class="Low",
            tool_class="B", sensitivity="Tier3", action_risk="R4",
        )
        self.assertTrue(_matches(rule, ctx))


class TestContextReasonCodes(unittest.TestCase):
    """Verify context-level reason codes are built correctly."""

    def test_build_context_reason_codes(self):
        ctx = PolicyContext(
            confidence=0.5,
            confidence_class="Medium",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R2",
        )
        codes = _build_context_reason_codes(ctx)
        self.assertEqual(codes, [
            "class_c_tool",
            "medium_confidence",
            "sensitivity_tier1",
            "action_risk_r2",
        ])


class TestFullEvaluatePolicyUsesDrivenEngine(unittest.TestCase):
    """Verify that the public evaluate_policy() function uses the data-driven
    engine and still produces identical results to the original."""

    def test_evaluate_policy_matches_original_for_each_tested_rule(self):
        """Re-run the exact test cases from test_policy.py through the public API."""
        # ENFORCE-005
        d = evaluate_policy(0.9, "High", "C", "Tier3", "R2", explicit_deny=True)
        self.assertEqual(d.decision_state, "block")
        self.assertEqual(d.rule_id, "ENFORCE-005")

        # ENFORCE-004
        d = evaluate_policy(0.8, "High", "C", "Tier1", "R4")
        self.assertEqual(d.decision_state, "block")
        self.assertEqual(d.rule_id, "ENFORCE-004")

        # ENFORCE-006
        d = evaluate_policy(0.6, "Medium", "C", "Tier1", "R3")
        self.assertEqual(d.decision_state, "approval_required")
        self.assertEqual(d.rule_id, "ENFORCE-006")

        # ENFORCE-003
        d = evaluate_policy(0.5, "Medium", "B", "Tier2", "R3")
        self.assertEqual(d.decision_state, "approval_required")
        self.assertEqual(d.rule_id, "ENFORCE-003")

        # ENFORCE-002
        d = evaluate_policy(0.5, "Medium", "A", "Tier1", "R2")
        self.assertEqual(d.decision_state, "warn")
        self.assertEqual(d.rule_id, "ENFORCE-002")

        # ENFORCE-001
        d = evaluate_policy(0.3, "Low", "A", "Tier0", "R1")
        self.assertEqual(d.decision_state, "detect")
        self.assertEqual(d.rule_id, "ENFORCE-001")

        # Fallbacks
        d = evaluate_policy(0.8, "High", "A", "Tier0", "R3")
        self.assertEqual(d.decision_state, "approval_required")
        self.assertEqual(d.rule_id, "ENFORCE-003-F")

        d = evaluate_policy(0.8, "High", "A", "Tier0", "R2")
        self.assertEqual(d.decision_state, "warn")
        self.assertEqual(d.rule_id, "ENFORCE-002-F")

        d = evaluate_policy(0.5, "Medium", "A", "Tier0", "R1")
        self.assertEqual(d.decision_state, "warn")
        self.assertEqual(d.rule_id, "ENFORCE-002-F")

        d = evaluate_policy(0.2, "Low", "B", "Tier2", "R3")
        self.assertEqual(d.decision_state, "detect")
        self.assertEqual(d.rule_id, "ENFORCE-001-F")


if __name__ == "__main__":
    unittest.main()
