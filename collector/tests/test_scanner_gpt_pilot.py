"""Integration tests for GPTPilotScanner with synthetic file fixtures and mocked subprocesses."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.gpt_pilot import GPTPilotScanner
from tests.fixtures.canned_responses import (
    EMPTY,
    GPT_PILOT_NOT_RUNNING,
    GPT_PILOT_RUNNING,
    make_dispatcher,
)
from tests.fixtures.file_fixtures import create_gpt_pilot_footprint


class TestGPTPilotCleanSystem(unittest.TestCase):
    """Scenario: no GPT-Pilot artifacts, no processes."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_system_not_detected(self):
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
        with (
            patch("scanner.gpt_pilot.HOME", self.home),
            patch.object(GPTPilotScanner, "_run_cmd", make_dispatcher(GPT_PILOT_NOT_RUNNING)),
            patch.dict(os.environ, env_clean, clear=True),
        ):
            scanner = GPTPilotScanner()
            result = scanner.scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)


class TestGPTPilotStateDirsOnly(unittest.TestCase):
    """Scenario: .gpt-pilot/ state dirs exist but no running process."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.workspace = create_gpt_pilot_footprint(
            self.home, with_state_dir=True, with_workspace=False, file_churn=0,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_state_dirs_detects_file_and_behavior(self):
        with (
            patch("scanner.gpt_pilot.HOME", self.home),
            patch.object(GPTPilotScanner, "_run_cmd", make_dispatcher(GPT_PILOT_NOT_RUNNING)),
        ):
            scanner = GPTPilotScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.75)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertGreaterEqual(result.signals.behavior, 0.60)
        self.assertIn("state_dirs", result.evidence_details)
        self.assertEqual(result.action_type, "read")
        self.assertEqual(result.action_risk, "R1")


class TestGPTPilotGenerationLoopActive(unittest.TestCase):
    """Scenario: GPT-Pilot running with child processes and high file churn."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.workspace = create_gpt_pilot_footprint(
            self.home, with_state_dir=True, with_workspace=True, file_churn=30,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_fully_active_all_layers(self):
        with (
            patch("scanner.gpt_pilot.HOME", self.home),
            patch.object(GPTPilotScanner, "_run_cmd", make_dispatcher(GPT_PILOT_RUNNING)),
        ):
            scanner = GPTPilotScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.process, 0.75)
        self.assertGreaterEqual(result.signals.file, 0.45)
        self.assertGreaterEqual(result.signals.identity, 0.40)
        self.assertGreaterEqual(result.signals.behavior, 0.80)
        self.assertEqual(result.tool_class, "C")
        self.assertEqual(result.action_type, "exec")
        self.assertIn(result.action_risk, ("R2", "R3"))
        self.assertTrue(result.evidence_details.get("generation_loop_active"))

    def test_high_file_churn_detected(self):
        """Workspace with >20 recent files triggers high-churn behavior signal."""
        with (
            patch("scanner.gpt_pilot.HOME", self.home),
            patch.object(GPTPilotScanner, "_run_cmd", make_dispatcher(GPT_PILOT_NOT_RUNNING)),
        ):
            scanner = GPTPilotScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.behavior, 0.60)


if __name__ == "__main__":
    unittest.main()
