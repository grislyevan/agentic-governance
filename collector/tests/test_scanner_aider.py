"""Integration tests for AiderScanner with synthetic file fixtures and mocked subprocesses."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scanner.aider import AiderScanner
from tests.fixtures.canned_responses import (
    AIDER_RUNNING,
    EMPTY,
    make_dispatcher,
)
from tests.fixtures.compat_fixtures import make_aider_compat_mocks
from tests.fixtures.file_fixtures import create_aider_footprint

# _run_cmd is only used for: pip show, aider --version, git config
AIDER_RUN_CMD_CLEAN = {
    ("pip", "show", "aider-chat"): EMPTY,
    ("aider", "--version"): EMPTY,
    ("git", "config", "--global", "user.email"): EMPTY,
}
AIDER_RUN_CMD_INSTALLED = {
    ("pip", "show", "aider-chat"): AIDER_RUNNING[("pip", "show", "aider-chat")],
    ("aider", "--version"): AIDER_RUNNING[("aider", "--version")],
    ("git", "config", "--global", "user.email"): AIDER_RUNNING[
        ("git", "config", "--global", "user.email")
    ],
}


class TestAiderCleanSystem(unittest.TestCase):
    """Scenario: no Aider artifacts, no processes — scanner reports nothing."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_system_not_detected(self):
        find_proc, get_children, get_info, get_conn = make_aider_compat_mocks(active=False)
        env_clean = {k: v for k, v in os.environ.items()
                     if k not in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY")}
        with (
            patch("scanner.aider.HOME", self.home),
            patch("scanner.aider.find_processes", find_proc),
            patch("scanner.aider.get_child_pids", get_children),
            patch("scanner.aider.get_process_info", get_info),
            patch("scanner.aider.get_connections", get_conn),
            patch.object(AiderScanner, "_run_cmd", make_dispatcher(AIDER_RUN_CMD_CLEAN)),
            patch.object(AiderScanner, "_find_aider_commits", return_value=[]),
            patch.dict(os.environ, env_clean, clear=True),
        ):
            scanner = AiderScanner()
            result = scanner.scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)


class TestAiderInstalledNotRunning(unittest.TestCase):
    """Scenario: .aider* artifacts and pip package present, but no running process."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.repo = create_aider_footprint(self.home, recent=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_installed_detects_file_layer(self):
        find_proc, get_children, get_info, get_conn = make_aider_compat_mocks(active=False)

        with (
            patch("scanner.aider.HOME", self.home),
            patch("scanner.aider.find_processes", find_proc),
            patch("scanner.aider.get_child_pids", get_children),
            patch("scanner.aider.get_process_info", get_info),
            patch("scanner.aider.get_connections", get_conn),
            patch.object(AiderScanner, "_run_cmd", make_dispatcher(AIDER_RUN_CMD_INSTALLED)),
            patch.object(AiderScanner, "_find_aider_commits", return_value=[]),
        ):
            scanner = AiderScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.50)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.network, 0.0)
        self.assertEqual(result.action_type, "read")
        self.assertEqual(result.action_risk, "R1")
        self.assertIn("pip_installed", result.evidence_details)


class TestAiderFullyActive(unittest.TestCase):
    """Scenario: Aider process running with child git/pytest, file artifacts, API connections."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.repo = create_aider_footprint(self.home, recent=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_fully_active_all_layers(self):
        find_proc, get_children, get_info, get_conn = make_aider_compat_mocks(active=True)
        with (
            patch("scanner.aider.HOME", self.home),
            patch("scanner.aider.find_processes", find_proc),
            patch("scanner.aider.get_child_pids", get_children),
            patch("scanner.aider.get_process_info", get_info),
            patch("scanner.aider.get_connections", get_conn),
            patch.object(AiderScanner, "_run_cmd", make_dispatcher(AIDER_RUN_CMD_INSTALLED)),
            patch.object(
                AiderScanner,
                "_find_aider_commits",
                return_value=[{"repo": str(self.repo), "commit_subject": "aider: fix tests"}],
            ),
        ):
            scanner = AiderScanner()
            result = scanner.scan(verbose=True)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.process, 0.75)
        self.assertGreaterEqual(result.signals.file, 0.50)
        self.assertGreaterEqual(result.signals.identity, 0.40)
        self.assertGreaterEqual(result.signals.behavior, 0.75)
        self.assertEqual(result.tool_class, "C")
        self.assertEqual(result.action_type, "exec")
        self.assertIn(result.action_risk, ("R2", "R3"))
        self.assertTrue(result.evidence_details.get("prompt_edit_loop_active"))
        self.assertIn("agentic_children", result.evidence_details)


class TestAiderGitCommitDetection(unittest.TestCase):
    """Scenario: Aider not running but git commits attributable to aider exist."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.repo = create_aider_footprint(self.home, recent=False)

    def tearDown(self):
        self._tmp.cleanup()

    def test_aider_commits_boost_behavior(self):
        find_proc, get_children, get_info, get_conn = make_aider_compat_mocks(active=False)
        commits = [{"repo": str(self.repo), "commit_subject": "aider: fix input validation"}]
        run_cmd = {
            ("pip", "show", "aider-chat"): EMPTY,
            ("aider", "--version"): EMPTY,
            ("git", "config", "--global", "user.email"): AIDER_RUNNING[
                ("git", "config", "--global", "user.email")
            ],
        }

        with (
            patch("scanner.aider.HOME", self.home),
            patch("scanner.aider.find_processes", find_proc),
            patch("scanner.aider.get_child_pids", get_children),
            patch("scanner.aider.get_process_info", get_info),
            patch("scanner.aider.get_connections", get_conn),
            patch.object(AiderScanner, "_run_cmd", make_dispatcher(run_cmd)),
            patch.object(AiderScanner, "_find_aider_commits", return_value=commits),
        ):
            scanner = AiderScanner()
            result = scanner.scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.behavior, 0.55)
        self.assertIn("aider_git_commits", result.evidence_details)


if __name__ == "__main__":
    unittest.main()
