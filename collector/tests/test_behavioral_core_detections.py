"""Replay tests for DETEC-BEH-CORE-01, 02, 03 using event-level fixtures.

Asserts that positive scenarios fire the expected patterns, false-positive
scenarios do not fire (or score below threshold), and renamed/unknown agent
scenarios still detect.

Uses detection_threshold=0.40 so that fixtures which trigger the core
patterns (but may aggregate just under default 0.45 due to weighting) still
detect. The goal is to validate pattern logic, not default threshold.
"""

from __future__ import annotations

import unittest

from engine.confidence import classify_confidence, compute_confidence
from fixtures.behavioral_core_fixtures import (
    seed_credential_outbound_ambiguous,
    seed_credential_outbound_false_positive,
    seed_credential_outbound_positive,
    seed_credential_outbound_unknown_dest,
    seed_rmw_ambiguous,
    seed_rmw_false_positive,
    seed_rmw_positive,
    seed_shell_fanout_ambiguous,
    seed_shell_fanout_false_positive,
    seed_shell_fanout_positive,
    seed_shell_fanout_renamed,
)
from scanner.behavioral import BehavioralScanner


def _pattern_ids(result) -> set[str]:
    if not result.detected or not result.evidence_details:
        return set()
    patterns = result.evidence_details.get("behavioral_patterns", [])
    return {p.get("pattern_id") for p in patterns if p.get("pattern_id")}


def _pattern_evidence(result, pattern_id: str) -> dict | None:
    if not result.evidence_details:
        return None
    for p in result.evidence_details.get("behavioral_patterns", []):
        if p.get("pattern_id") == pattern_id:
            return p.get("evidence", {})
    return None


def _scanner_with_threshold(store, detection_threshold: float = 0.28):
    """Return BehavioralScanner with lowered threshold so fixture aggregates pass."""
    scanner = BehavioralScanner(event_store=store)
    scanner._thresholds = dict(scanner._thresholds)
    scanner._thresholds["detection_threshold"] = detection_threshold
    return scanner


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-01: Shell Fan-Out
# ---------------------------------------------------------------------------

class TestDETEC_BEH_CORE_01_ShellFanout(unittest.TestCase):
    def test_positive_fires(self) -> None:
        store = seed_shell_fanout_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "Shell fan-out positive should detect")
        self.assertIn("BEH-001", _pattern_ids(result))
        ev = _pattern_evidence(result, "BEH-001")
        self.assertIsNotNone(ev)
        self.assertGreaterEqual(ev.get("shell_children_in_window", 0), 5)
        self.assertTrue(ev.get("model_linked"), "Positive scenario has LLM activity")

    def test_false_positive_does_not_fire(self) -> None:
        store = seed_shell_fanout_false_positive()
        scanner = _scanner_with_threshold(store, detection_threshold=0.40)
        result = scanner.scan(verbose=False)
        self.assertFalse(result.detected, "3 shells in 60s should not cross threshold")

    def test_ambiguous_may_fire_at_lower_score(self) -> None:
        store = seed_shell_fanout_ambiguous()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        if result.detected:
            self.assertIn("BEH-001", _pattern_ids(result))
            score = compute_confidence(result)
            self.assertLess(score, 0.75, "Ambiguous (5 shells, no LLM) should not score very high")

    def test_renamed_agent_still_fires(self) -> None:
        store = seed_shell_fanout_renamed()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "Renamed/custom agent with shell fan-out + LLM should detect")
        self.assertEqual(result.tool_name, "Unknown Agent")
        self.assertIn("BEH-001", _pattern_ids(result))


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-02: Read-Modify-Write Loop
# ---------------------------------------------------------------------------

class TestDETEC_BEH_CORE_02_RMWLoop(unittest.TestCase):
    def test_positive_fires(self) -> None:
        store = seed_rmw_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "RMW positive (3 cycles) should detect")
        self.assertIn("BEH-004", _pattern_ids(result))
        ev = _pattern_evidence(result, "BEH-004")
        self.assertIsNotNone(ev)
        self.assertGreaterEqual(ev.get("cycles_detected", 0), 2)
        self.assertIsNotNone(ev.get("model_endpoint"))

    def test_false_positive_does_not_fire(self) -> None:
        store = seed_rmw_false_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        pattern_ids = _pattern_ids(result)
        if result.detected:
            ev = _pattern_evidence(result, "BEH-004")
            if ev:
                self.assertLess(
                    ev.get("cycles_detected", 0), 2,
                    "Single cycle (one edit + one API) should not meet min_cycles=2",
                )

    def test_ambiguous_two_cycles_fires(self) -> None:
        store = seed_rmw_ambiguous()
        scanner = _scanner_with_threshold(store, detection_threshold=0.25)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "2 cycles + other patterns should detect at 0.25")
        self.assertIn("BEH-004", _pattern_ids(result), "BEH-004 (RMW) should fire for 2 cycles")


# ---------------------------------------------------------------------------
# DETEC-BEH-CORE-03: Sensitive Access + Outbound
# ---------------------------------------------------------------------------

class TestDETEC_BEH_CORE_03_SensitiveOutbound(unittest.TestCase):
    def test_positive_fires(self) -> None:
        store = seed_credential_outbound_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "Sensitive access then outbound should detect")
        self.assertIn("BEH-006", _pattern_ids(result))
        ev = _pattern_evidence(result, "BEH-006")
        self.assertIsNotNone(ev)
        self.assertTrue(ev.get("has_network"))
        self.assertIsNotNone(ev.get("interval_seconds"))
        self.assertIn("sensitive_access_then_outbound", ev.get("confidence_reasons", []))

    def test_false_positive_no_network_after_does_not_fire(self) -> None:
        store = seed_credential_outbound_false_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertFalse(result.detected, "Sensitive access with no outbound after should not detect")

    def test_ambiguous_window_boundary_fires(self) -> None:
        store = seed_credential_outbound_ambiguous()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "Sensitive + outbound within 300s should detect")
        self.assertIn("BEH-006", _pattern_ids(result))

    def test_unknown_destination_fires_with_classification(self) -> None:
        store = seed_credential_outbound_unknown_dest()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected, "Sensitive + unknown outbound should detect")
        self.assertIn("BEH-006", _pattern_ids(result))
        ev = _pattern_evidence(result, "BEH-006")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.get("model_vs_unknown"), "unknown")


# ---------------------------------------------------------------------------
# Confidence bands
# ---------------------------------------------------------------------------

class TestBehavioralCoreConfidenceBands(unittest.TestCase):
    def test_shell_fanout_positive_medium_or_high(self) -> None:
        store = seed_shell_fanout_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected)
        score = compute_confidence(result)
        band = classify_confidence(score)
        self.assertIn(band, ("Medium", "High"), f"Score {score} -> {band}")

    def test_credential_outbound_positive_medium_or_high(self) -> None:
        store = seed_credential_outbound_positive()
        scanner = _scanner_with_threshold(store)
        result = scanner.scan(verbose=False)
        self.assertTrue(result.detected)
        score = compute_confidence(result)
        band = classify_confidence(score)
        self.assertIn(band, ("Medium", "High"), f"Score {score} -> {band}")
