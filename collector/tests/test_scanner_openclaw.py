"""Unit tests for OpenClawScanner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo, ProcessInfo, ToolPaths
from scanner.openclaw import OpenClawScanner


class TestOpenClawScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.data_dir = self.home / ".openclaw"
        (self.data_dir / "workspace" / "skills" / "s1").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "openclaw.json").write_text(json.dumps({"agents": {"defaults": {"model": {"primary": "ollama/llama3"}}}}))
        self.paths = ToolPaths(data_dir=self.data_dir)
        self.plist = self.home / "ai.openclaw.gateway.plist"
        self.plist.write_text("plist")

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_detection_daemon_running(self):
        proc = ProcessInfo(pid=8101, name="node", cmdline="openclaw gateway start", username="u", ppid=1)
        listener = ConnectionInfo(pid=8101, local_addr="127.0.0.1", local_port=18789, remote_addr=None, remote_port=None, status="LISTEN")

        with (
            patch("scanner.openclaw.get_tool_paths", return_value=self.paths),
            patch("scanner.openclaw.find_processes", return_value=[proc]),
            patch("scanner.openclaw.get_process_info", return_value=proc),
            patch("scanner.openclaw.get_listeners", return_value=[listener]),
            patch("scanner.openclaw.get_connections", return_value=[]),
            patch("scanner.openclaw.LAUNCH_AGENT_PLIST", self.plist),
            patch.object(OpenClawScanner, "_check_launch_agent", return_value=False),
            patch.object(OpenClawScanner, "_run_cmd", return_value=None),
        ):
            result = OpenClawScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.action_type, "exec")
        self.assertEqual(result.action_risk, "R3")
        self.assertTrue(result.evidence_details.get("self_modification_evidence"))

    def test_negative_no_signal(self):
        empty_paths = ToolPaths(data_dir=self.home / "none")
        with (
            patch("scanner.openclaw.get_tool_paths", return_value=empty_paths),
            patch("scanner.openclaw.find_processes", return_value=[]),
            patch("scanner.openclaw.get_process_info", return_value=None),
            patch("scanner.openclaw.get_listeners", return_value=[]),
            patch("scanner.openclaw.get_connections", return_value=[]),
            patch("scanner.openclaw.LAUNCH_AGENT_PLIST", self.home / "none.plist"),
            patch.object(OpenClawScanner, "_run_cmd", return_value=None),
        ):
            result = OpenClawScanner().scan(verbose=False)

        self.assertFalse(result.detected)

    def test_stale_artifact_penalty(self):
        with (
            patch("scanner.openclaw.get_tool_paths", return_value=self.paths),
            patch("scanner.openclaw.find_processes", return_value=[]),
            patch("scanner.openclaw.get_process_info", return_value=None),
            patch("scanner.openclaw.get_listeners", return_value=[]),
            patch("scanner.openclaw.get_connections", return_value=[]),
            patch("scanner.openclaw.LAUNCH_AGENT_PLIST", self.home / "none.plist"),
            patch.object(OpenClawScanner, "_run_cmd", return_value=None),
        ):
            result = OpenClawScanner().scan(verbose=False)

        self.assertIn(("stale_artifact_only", 0.10), result.penalties)
        self.assertTrue(result.detected)

    def test_process_network_linkage_penalty(self):
        proc = ProcessInfo(pid=8201, name="node", cmdline="openclaw gateway start", username="u", ppid=1)
        listener = ConnectionInfo(pid=9999, local_addr="127.0.0.1", local_port=18789, remote_addr=None, remote_port=None, status="LISTEN")

        with (
            patch("scanner.openclaw.get_tool_paths", return_value=self.paths),
            patch("scanner.openclaw.find_processes", return_value=[proc]),
            patch("scanner.openclaw.get_process_info", return_value=proc),
            patch("scanner.openclaw.get_listeners", return_value=[listener]),
            patch("scanner.openclaw.get_connections", return_value=[]),
            patch("scanner.openclaw.LAUNCH_AGENT_PLIST", self.home / "none.plist"),
            patch.object(OpenClawScanner, "_check_launch_agent", return_value=False),
            patch.object(OpenClawScanner, "_run_cmd", return_value=None),
        ):
            result = OpenClawScanner().scan(verbose=False)

        self.assertIn(("unresolved_process_network_linkage", 0.05), result.penalties)


if __name__ == "__main__":
    unittest.main()
