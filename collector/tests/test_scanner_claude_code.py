"""Unit tests for ClaudeCodeScanner."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ProcessInfo
from scanner.claude_code import ClaudeCodeScanner


class TestClaudeCodeScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_active_detection(self):
        (self.home / ".claude").mkdir(parents=True, exist_ok=True)
        settings = self.home / ".claude" / "settings.json"
        settings.write_text(json.dumps({"includeCoAuthoredBy": True}))

        procs = [
            ProcessInfo(pid=41001, name="claude", cmdline="claude --print", username="tester", ppid=1),
        ]

        with (
            patch("scanner.claude_code.Path.home", return_value=self.home),
            patch("scanner.claude_code.find_processes", return_value=procs),
            patch("scanner.claude_code.get_child_pids", return_value=[41002]),
            patch(
                "scanner.claude_code.get_process_info",
                side_effect=lambda pid: ProcessInfo(
                    pid=pid,
                    name="bash",
                    cmdline="bash -lc git status",
                    username="tester",
                    ppid=41001,
                ),
            ),
            patch("scanner.claude_code.ClaudeCodeScanner._find_coauthored_trailers", return_value=[]),
            patch.object(ClaudeCodeScanner, "_run_cmd", return_value=None),
        ):
            result = ClaudeCodeScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.process, 0.85)
        self.assertGreaterEqual(result.signals.behavior, 0.75)
        self.assertEqual(result.action_type, "exec")

    def test_negative_no_signal(self):
        with (
            patch("scanner.claude_code.Path.home", return_value=self.home),
            patch("scanner.claude_code.find_processes", return_value=[]),
            patch("scanner.claude_code.ClaudeCodeScanner._find_coauthored_trailers", return_value=[]),
            patch.object(ClaudeCodeScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = ClaudeCodeScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)

    def test_stale_artifacts_penalty(self):
        (self.home / ".claude").mkdir(parents=True, exist_ok=True)
        old_file = self.home / ".claude" / "old.log"
        old_file.write_text("x")
        stale = time.time() - 3 * 86400
        old_file.chmod(0o644)
        import os
        os.utime(old_file, (stale, stale))

        with (
            patch("scanner.claude_code.Path.home", return_value=self.home),
            patch("scanner.claude_code.find_processes", return_value=[]),
            patch("scanner.claude_code.ClaudeCodeScanner._find_coauthored_trailers", return_value=[]),
            patch.object(ClaudeCodeScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = ClaudeCodeScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertIn(("stale_artifact_only", 0.10), result.penalties)

    def test_evasion_indicator_boost(self):
        (self.home / ".claude").mkdir(parents=True, exist_ok=True)
        settings = self.home / ".claude" / "settings.json"
        settings.write_text(json.dumps({"includeCoAuthoredBy": False}))

        with (
            patch("scanner.claude_code.Path.home", return_value=self.home),
            patch("scanner.claude_code.find_processes", return_value=[]),
            patch("scanner.claude_code.ClaudeCodeScanner._find_coauthored_trailers", return_value=[]),
            patch.object(ClaudeCodeScanner, "_run_cmd", return_value=None),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = ClaudeCodeScanner().scan(verbose=False)

        self.assertGreater(result.evasion_boost, 0.0)
        self.assertIn("evasion_indicators", result.evidence_details)


if __name__ == "__main__":
    unittest.main()
