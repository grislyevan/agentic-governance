"""Unit tests for CopilotScanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo, ProcessInfo, ToolPaths
from scanner.copilot import CopilotScanner


class TestCopilotScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.ext_dir = self.home / ".vscode" / "extensions" / "github.copilot-chat-1.0.0"
        self.ext_dir.mkdir(parents=True, exist_ok=True)
        (self.ext_dir / "package.json").write_text('{"version":"1.0.0"}')
        self.log_dir = self.home / "logs"
        auth = self.log_dir / "s1" / "vscode.github-authentication"
        auth.mkdir(parents=True, exist_ok=True)
        (auth / "GitHub Authentication.log").write_text("Got 1 sessions")
        self.paths = ToolPaths(
            config_dir=self.home / "codecfg",
            data_dir=self.home / ".vscode",
            extensions_dir=self.home / ".vscode" / "extensions",
            log_dir=self.log_dir,
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_detection_authenticated(self):
        procs = [
            ProcessInfo(pid=6101, name="Code", cmdline="Visual Studio Code", username="u", ppid=1),
            ProcessInfo(pid=6102, name="Code Helper", cmdline="Code Helper (Plugin)", username="u", ppid=6101),
        ]

        with (
            patch("scanner.copilot.get_tool_paths", return_value=self.paths),
            patch("scanner.copilot.find_processes", return_value=procs),
            patch("scanner.copilot.get_connections", return_value=[ConnectionInfo(pid=6101, local_addr="127.0.0.1", local_port=55001, remote_addr="140.82.121.4", remote_port=443, status="ESTABLISHED")]),
            patch("scanner.copilot.get_credential_store_entry", return_value=True),
        ):
            result = CopilotScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.85)
        self.assertGreaterEqual(result.signals.identity, 0.8)
        self.assertEqual(result.action_risk, "R2")

    def test_negative_no_signal(self):
        empty_paths = ToolPaths(config_dir=self.home / "none", data_dir=self.home / "none", extensions_dir=self.home / "none", log_dir=self.home / "none")
        with (
            patch("scanner.copilot.get_tool_paths", return_value=empty_paths),
            patch("scanner.copilot.find_processes", return_value=[]),
            patch("scanner.copilot.get_connections", return_value=[]),
            patch("scanner.copilot.get_credential_store_entry", return_value=False),
        ):
            result = CopilotScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)
        self.assertEqual(result.signals.network, 0.0)

    def test_stale_artifacts_vs_active_process(self):
        unauth_log_dir = self.home / "logs2"
        auth = unauth_log_dir / "s1" / "vscode.github-authentication"
        auth.mkdir(parents=True, exist_ok=True)
        (auth / "GitHub Authentication.log").write_text("Got 0 sessions")
        stale_paths = ToolPaths(
            config_dir=self.home / "codecfg2",
            data_dir=self.home / ".vscode",
            extensions_dir=self.home / ".vscode" / "extensions",
            log_dir=unauth_log_dir,
        )

        with (
            patch("scanner.copilot.get_tool_paths", return_value=stale_paths),
            patch("scanner.copilot.find_processes", return_value=[]),
            patch("scanner.copilot.get_connections", return_value=[]),
            patch("scanner.copilot.get_credential_store_entry", return_value=False),
        ):
            result = CopilotScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertGreater(result.signals.file, 0.0)
        self.assertEqual(result.action_risk, "R1")

    def test_confidence_penalties(self):
        procs = [
            ProcessInfo(pid=6201, name="Code", cmdline="Visual Studio Code", username="u", ppid=1),
            ProcessInfo(pid=6202, name="Code Helper", cmdline="Code Helper (Plugin)", username="u", ppid=6201),
        ]
        with (
            patch("scanner.copilot.get_tool_paths", return_value=self.paths),
            patch("scanner.copilot.find_processes", return_value=procs),
            patch("scanner.copilot.get_connections", return_value=[ConnectionInfo(pid=6201, local_addr="127.0.0.1", local_port=55003, remote_addr="20.1.1.1", remote_port=443, status="ESTABLISHED")]),
            patch("scanner.copilot.get_credential_store_entry", return_value=False),
        ):
            result = CopilotScanner().scan(verbose=False)

        self.assertIn(("extension_host_shared_by_all_extensions", 0.05), result.penalties)
        self.assertIn(("unresolved_copilot_vs_vscode_traffic", 0.05), result.penalties)


if __name__ == "__main__":
    unittest.main()
