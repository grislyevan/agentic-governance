"""Tests for collector/engine/confidence.py: compute_confidence and classify_confidence."""

import unittest

from engine.confidence import (
    classify_confidence,
    compute_confidence,
    get_weights,
    DEFAULT_WEIGHTS,
    TOOL_WEIGHTS,
)
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
        # Ollama: process 0.25, file 0.25, network 0.20, identity 0.10, behavior 0.20
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
            signals=LayerSignals(1.0, 1.0, 0, 0, 0),  # Cursor: 0.30 + 0.20 = 0.5
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


if __name__ == "__main__":
    unittest.main()
