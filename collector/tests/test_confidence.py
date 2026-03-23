"""Tests for collector/engine/confidence.py: compute_confidence and classify_confidence.

INIT-31-E2-05: Evasion boost stays bounded; policy outcomes deterministic when evasion vectors fire.
"""

import unittest

from engine.confidence import (
    classify_confidence,
    compute_confidence,
    get_weights,
    DEFAULT_WEIGHTS,
    TOOL_WEIGHTS,
)
from engine.policy import evaluate_policy
from scanner.base import LayerSignals, ScanResult


class TestClassifyConfidence(unittest.TestCase):
    """Test Low/Medium/High classification per Playbook Section 6.2."""

    def test_high_threshold(self):
        self.assertEqual(classify_confidence(0.75), "High")
        self.assertEqual(classify_confidence(0.80), "High")
        self.assertEqual(classify_confidence(1.0), "High")

    def test_medium_range(self):
        self.assertEqual(classify_confidence(0.45), "Medium")
        self.assertEqual(classify_confidence(0.50), "Medium")
        self.assertEqual(classify_confidence(0.74), "Medium")

    def test_low_below_medium(self):
        self.assertEqual(classify_confidence(0.44), "Low")
        self.assertEqual(classify_confidence(0.0), "Low")


class TestGetWeights(unittest.TestCase):
    """Test per-tool weight lookup."""

    def test_known_tools(self):
        self.assertEqual(get_weights("Ollama"), TOOL_WEIGHTS["Ollama"])
        self.assertEqual(get_weights("Cursor"), TOOL_WEIGHTS["Cursor"])
        self.assertEqual(get_weights("GitHub Copilot"), TOOL_WEIGHTS["GitHub Copilot"])
        self.assertEqual(get_weights("Open Interpreter"), TOOL_WEIGHTS["Open Interpreter"])

    def test_unknown_or_none_uses_default(self):
        self.assertEqual(get_weights(None), DEFAULT_WEIGHTS)
        self.assertEqual(get_weights("Unknown Tool"), DEFAULT_WEIGHTS)


class TestComputeConfidence(unittest.TestCase):
    """Test confidence score formula with known LayerSignals and tool weights."""

    def test_zero_signals_zero_confidence(self):
        scan = ScanResult(
            detected=True,
            tool_name="Ollama",
            tool_class="B",
            signals=LayerSignals(0, 0, 0, 0, 0),
            penalties=[],
            evasion_boost=0.0,
        )
        self.assertEqual(compute_confidence(scan), 0.0)

    def test_full_signals_default_weights_no_penalty(self):
        # Weights sum to 1.0; all signals 1.0 => base_score = 1.0
        scan = ScanResult(
            detected=True,
            tool_name=None,
            tool_class="A",
            signals=LayerSignals(1.0, 1.0, 1.0, 1.0, 1.0),
            penalties=[],
            evasion_boost=0.0,
        )
        self.assertEqual(compute_confidence(scan), 1.0)

    def test_ollama_weights_known_signals(self):
        # Ollama: process 0.25, file 0.25, network 0.25, identity 0.05, behavior 0.20
        # process=1, file=1, rest=0 => 0.25 + 0.25 = 0.5
        scan = ScanResult(
            detected=True,
            tool_name="Ollama",
            tool_class="B",
            signals=LayerSignals(process=1.0, file=1.0, network=0, identity=0, behavior=0),
            penalties=[],
            evasion_boost=0.0,
        )
        self.assertEqual(compute_confidence(scan), 0.5)

    def test_penalties_reduce_score(self):
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(1.0, 1.0, 0, 0, 0),  # Cursor: process 0.30 + file 0.20 = 0.5
            penalties=[("some_penalty", 0.1)],
            evasion_boost=0.0,
        )
        self.assertEqual(compute_confidence(scan), 0.4)

    def test_evasion_boost_increases_score(self):
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(0.5, 0.5, 0, 0, 0),  # 0.15 + 0.10 = 0.25
            penalties=[],
            evasion_boost=0.1,
        )
        self.assertEqual(compute_confidence(scan), 0.35)

    def test_final_score_clamped_to_one(self):
        scan = ScanResult(
            detected=True,
            tool_name=None,
            signals=LayerSignals(1.0, 1.0, 1.0, 1.0, 1.0),
            penalties=[],
            evasion_boost=0.5,
        )
        self.assertEqual(compute_confidence(scan), 1.0)

    def test_final_score_clamped_to_zero(self):
        scan = ScanResult(
            detected=True,
            tool_name="Ollama",
            signals=LayerSignals(0.2, 0.2, 0, 0, 0),
            penalties=[("p", 0.5)],
            evasion_boost=0.0,
        )
        self.assertEqual(compute_confidence(scan), 0.0)

    def test_result_rounded_to_four_decimals(self):
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            signals=LayerSignals(0.3333, 0.3333, 0.3334, 0, 0),
            penalties=[],
            evasion_boost=0.0,
        )
        score = compute_confidence(scan)
        self.assertIsInstance(score, float)
        self.assertEqual(round(score, 4), score)

    def test_evasion_boost_stays_bounded(self):
        """INIT-31-E2-05: Evasion boost cannot push final score above 1.0."""
        # Base 0.5 + evasion 0.5 => 1.0 (capped)
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(0.5, 0.5, 0, 0, 0),  # 0.15 + 0.10 = 0.25 base
            penalties=[],
            evasion_boost=0.50,
        )
        score = compute_confidence(scan)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(score, 0.75)  # 0.25 + 0.50 = 0.75

    def test_evasion_boost_capped_contribution(self):
        """Scanner caps total evasion_boost at 0.50; formula clamps final to [0, 1]."""
        scan = ScanResult(
            detected=True,
            tool_name=None,
            tool_class="A",
            signals=LayerSignals(1.0, 1.0, 1.0, 1.0, 1.0),
            penalties=[],
            evasion_boost=0.50,
        )
        score = compute_confidence(scan)
        self.assertEqual(score, 1.0)

    def test_evasion_boost_deterministic_same_inputs_same_score(self):
        """Same scan inputs (including evasion_boost) produce same confidence and classification."""
        scan = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(0.6, 0.5, 0, 0.2, 0.3),
            penalties=[],
            evasion_boost=0.12,
        )
        s1 = compute_confidence(scan)
        c1 = classify_confidence(s1)
        s2 = compute_confidence(scan)
        c2 = classify_confidence(s2)
        self.assertEqual(s1, s2)
        self.assertEqual(c1, c2)


class TestEvasionPolicyDeterminism(unittest.TestCase):
    """INIT-31-E2-05: Policy outcomes deterministic when evasion vectors fire."""

    def test_same_confidence_same_policy_decision(self):
        """Same confidence and class yield same policy decision."""
        pol1 = evaluate_policy(
            confidence=0.72,
            confidence_class="High",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R2",
            is_containerized=False,
            net_ctx=None,
        )
        pol2 = evaluate_policy(
            confidence=0.72,
            confidence_class="High",
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R2",
            is_containerized=False,
            net_ctx=None,
        )
        self.assertEqual(pol1.decision_state, pol2.decision_state)
        self.assertEqual(pol1.rule_id, pol2.rule_id)

    def test_evasion_boost_affects_confidence_then_policy_stable(self):
        """With evasion boost, confidence rises but policy decision is deterministic for that score."""
        scan_no_evasion = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(0.5, 0.5, 0, 0, 0),
            penalties=[],
            evasion_boost=0.0,
        )
        scan_with_evasion = ScanResult(
            detected=True,
            tool_name="Cursor",
            tool_class="C",
            signals=LayerSignals(0.5, 0.5, 0, 0, 0),
            penalties=[],
            evasion_boost=0.15,
        )
        conf_no = compute_confidence(scan_no_evasion)
        conf_ev = compute_confidence(scan_with_evasion)
        self.assertGreater(conf_ev, conf_no)
        class_ev = classify_confidence(conf_ev)
        pol = evaluate_policy(
            confidence=conf_ev,
            confidence_class=class_ev,
            tool_class="C",
            sensitivity="Tier1",
            action_risk="R2",
            is_containerized=False,
            net_ctx=None,
        )
        self.assertIn(pol.decision_state, ("detect", "warn", "approval_required", "block"))


if __name__ == "__main__":
    unittest.main()
