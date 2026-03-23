"""Tests for telemetry diagnostics accumulator."""

from __future__ import annotations

from unittest import TestCase

from telemetry.diagnostics import DiagnosticsAccumulator


class TestDiagnosticsAccumulator(TestCase):
    def test_get_status_before_scan_has_zero_uptime(self) -> None:
        acc = DiagnosticsAccumulator()
        status = acc.get_status(provider_name="polling")
        self.assertEqual(status["uptime_seconds"], 0)
        self.assertEqual(status["provider"], "polling")

    def test_start_end_scan_populates_status(self) -> None:
        acc = DiagnosticsAccumulator()
        acc.start_scan()
        acc.end_scan(trees_count=5, patterns_triggered=["BEH-001", "BEH-006"])
        status = acc.get_status(provider_name="esf")
        self.assertGreaterEqual(status["uptime_seconds"], 0)
        self.assertEqual(status["trees_per_scan"], 5)
        self.assertEqual(status["patterns_triggered"], ["BEH-001", "BEH-006"])
        self.assertEqual(status["provider"], "esf")

    def test_get_status_includes_events_in_store_when_provided(self) -> None:
        acc = DiagnosticsAccumulator()
        acc.start_scan()
        acc.end_scan(trees_count=0, patterns_triggered=[])
        status = acc.get_status(
            provider_name="polling",
            event_counts={"process": 10, "network": 2, "file": 0, "file_read": 1},
        )
        self.assertIn("events_in_store", status)
        self.assertEqual(status["events_in_store"], {"process": 10, "network": 2, "file": 0, "file_read": 1})

    def test_get_status_includes_capability_drift_when_provided(self) -> None:
        acc = DiagnosticsAccumulator()
        status = acc.get_status(
            provider_name="polling",
            capability_drift=["file_read", "network_events"],
        )
        self.assertIn("capability_drift", status)
        self.assertEqual(status["capability_drift"], ["file_read", "network_events"])

    def test_get_status_includes_tamper_vectors_when_provided(self) -> None:
        acc = DiagnosticsAccumulator()
        status = acc.get_status(
            provider_name="polling",
            tamper_vectors=["E1-global-hook", "E6-agent-kill-loop"],
        )
        self.assertIn("tamper_vectors", status)
        self.assertEqual(
            status["tamper_vectors"], ["E1-global-hook", "E6-agent-kill-loop"]
        )

    def test_get_status_omits_tamper_vectors_when_empty(self) -> None:
        acc = DiagnosticsAccumulator()
        status = acc.get_status(
            provider_name="polling",
            tamper_vectors=[],
        )
        self.assertNotIn("tamper_vectors", status)
