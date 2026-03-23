"""Unit tests for OllamaScanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo, ProcessInfo, ToolPaths
from scanner.ollama import OllamaScanner


class TestOllamaScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.data_dir = self.home / ".ollama"
        self.models = self.data_dir / "models" / "manifests" / "registry.ollama.ai" / "library" / "llama3"
        self.models.mkdir(parents=True, exist_ok=True)
        (self.models / "latest").write_text("manifest")
        self.paths = ToolPaths(data_dir=self.data_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_detection_active_daemon(self):
        proc = ProcessInfo(pid=7101, name="ollama", cmdline="ollama serve", username="u", ppid=1)
        listener = ConnectionInfo(pid=7101, local_addr="127.0.0.1", local_port=11434, remote_addr=None, remote_port=None, status="LISTEN")

        with (
            patch("scanner.ollama.get_tool_paths", return_value=self.paths),
            patch("scanner.ollama.find_processes", return_value=[proc]),
            patch("scanner.ollama.get_listeners", return_value=[listener]),
            patch("scanner.ollama.get_service", return_value=None),
            patch("scanner.ollama.user_exists", return_value=True),
            patch.object(OllamaScanner, "_query_api", side_effect=["ok", '{"models":[{"name":"llama3:latest","size":1}]}']),
            patch.object(OllamaScanner, "_run_cmd", return_value=None),
        ):
            result = OllamaScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertTrue(result.evidence_details.get("daemon_running"))
        self.assertGreaterEqual(result.signals.network, 0.75)
        self.assertEqual(result.action_type, "exec")

    def test_negative_no_signal(self):
        empty = ToolPaths(data_dir=self.home / "none")
        with (
            patch("scanner.ollama.get_tool_paths", return_value=empty),
            patch("scanner.ollama.find_processes", return_value=[]),
            patch("scanner.ollama.get_listeners", return_value=[]),
            patch("scanner.ollama.get_service", return_value=None),
            patch("scanner.ollama.user_exists", return_value=False),
            patch.object(OllamaScanner, "_run_cmd", return_value=None),
        ):
            result = OllamaScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.file, 0.0)

    def test_stale_artifact_penalty(self):
        with (
            patch("scanner.ollama.get_tool_paths", return_value=self.paths),
            patch("scanner.ollama.find_processes", return_value=[]),
            patch("scanner.ollama.get_listeners", return_value=[]),
            patch("scanner.ollama.get_service", return_value=None),
            patch("scanner.ollama.user_exists", return_value=False),
            patch.object(OllamaScanner, "_run_cmd", return_value=None),
        ):
            result = OllamaScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertIn(("stale_artifact_only", 0.1), result.penalties)

    def test_process_network_linkage_penalty(self):
        proc = ProcessInfo(pid=7201, name="ollama", cmdline="ollama serve", username="u", ppid=1)
        listener = ConnectionInfo(pid=9999, local_addr="127.0.0.1", local_port=11434, remote_addr=None, remote_port=None, status="LISTEN")

        with (
            patch("scanner.ollama.get_tool_paths", return_value=self.paths),
            patch("scanner.ollama.find_processes", return_value=[proc]),
            patch("scanner.ollama.get_listeners", return_value=[listener]),
            patch("scanner.ollama.get_service", return_value=None),
            patch("scanner.ollama.user_exists", return_value=True),
            patch.object(OllamaScanner, "_query_api", return_value="ok"),
            patch.object(OllamaScanner, "_run_cmd", return_value=None),
        ):
            result = OllamaScanner().scan(verbose=False)

        self.assertIn(("unresolved_process_network_linkage", 0.10), result.penalties)


if __name__ == "__main__":
    unittest.main()
