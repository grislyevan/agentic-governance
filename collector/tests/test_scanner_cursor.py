"""Unit tests for CursorScanner."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo, ProcessInfo, ToolPaths
from scanner.cursor import CursorScanner


class TestCursorScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.data_dir = self.home / ".cursor"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tool_paths = ToolPaths(
            install_dir=self.home / "Applications" / "Cursor.app",
            config_dir=self.home / "Library" / "Application Support" / "Cursor",
            data_dir=self.data_dir,
            extensions_dir=self.data_dir / "extensions",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_positive_agent_exec_detection(self):
        transcripts = self.data_dir / "projects" / "p1" / "agent-transcripts" / "s1"
        transcripts.mkdir(parents=True, exist_ok=True)
        (transcripts / "a.jsonl").write_text("{}\n")

        cursor_proc = ProcessInfo(pid=5001, name="Cursor", cmdline="Cursor --type=renderer", username="u", ppid=1)
        agent_exec = ProcessInfo(pid=5002, name="Cursor", cmdline="Cursor extension-host agent-exec", username="u", ppid=5001)

        def find_processes(name: str):
            if name == "Cursor":
                return [cursor_proc, agent_exec]
            if name == "cursorsan":
                return []
            return []

        with (
            patch("scanner.cursor.get_tool_paths", return_value=self.tool_paths),
            patch("scanner.cursor.find_processes", side_effect=find_processes),
            patch("scanner.cursor.get_child_pids", return_value=[5003]),
            patch(
                "scanner.cursor.get_process_info",
                side_effect=lambda pid: ProcessInfo(pid=pid, name="bash", cmdline="bash -lc make test", username="u", ppid=5002),
            ),
            patch("scanner.cursor.get_connections", return_value=[ConnectionInfo(pid=5002, local_addr="127.0.0.1", local_port=54001, remote_addr="1.1.1.1", remote_port=443, status="ESTABLISHED")]),
            patch("scanner.cursor.verify_code_signature", return_value=None),
            patch.object(CursorScanner, "_run_cmd", return_value=None),
            patch.object(CursorScanner, "_find_madewith_trailers", return_value=[]),
        ):
            result = CursorScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.tool_class, "C")
        self.assertEqual(result.action_risk, "R3")
        self.assertGreaterEqual(result.signals.behavior, 0.85)

    def test_negative_no_signal(self):
        empty_paths = ToolPaths(data_dir=self.home / "none", config_dir=self.home / "none", install_dir=self.home / "none")
        with (
            patch("scanner.cursor.get_tool_paths", return_value=empty_paths),
            patch("scanner.cursor.find_processes", return_value=[]),
            patch("scanner.cursor.get_connections", return_value=[]),
            patch("scanner.cursor.verify_code_signature", return_value=None),
            patch.object(CursorScanner, "_run_cmd", return_value=None),
            patch.object(CursorScanner, "_find_madewith_trailers", return_value=[]),
        ):
            result = CursorScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.file, 0.0)

    def test_stale_artifact_vs_active_behavior(self):
        transcript = self.data_dir / "projects" / "p1" / "agent-transcripts" / "s1" / "stale.jsonl"
        transcript.parent.mkdir(parents=True, exist_ok=True)
        transcript.write_text("{}\n")
        old = time.time() - 2 * 3600
        import os
        os.utime(transcript, (old, old))

        with (
            patch("scanner.cursor.get_tool_paths", return_value=self.tool_paths),
            patch("scanner.cursor.find_processes", return_value=[]),
            patch("scanner.cursor.get_connections", return_value=[]),
            patch("scanner.cursor.verify_code_signature", return_value=None),
            patch.object(CursorScanner, "_run_cmd", return_value=None),
            patch.object(CursorScanner, "_find_madewith_trailers", return_value=[]),
        ):
            result = CursorScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.signals.behavior, 0.0)
        self.assertGreaterEqual(result.signals.file, 0.9)

    def test_confidence_penalty_weak_identity(self):
        cursor_proc = ProcessInfo(pid=5010, name="Cursor", cmdline="Cursor --type=renderer", username="u", ppid=1)

        def find_processes(name: str):
            return [cursor_proc] if name == "Cursor" else []

        with (
            patch("scanner.cursor.get_tool_paths", return_value=self.tool_paths),
            patch("scanner.cursor.find_processes", side_effect=find_processes),
            patch("scanner.cursor.get_connections", return_value=[]),
            patch("scanner.cursor.get_process_info", return_value=None),
            patch("scanner.cursor.verify_code_signature", return_value=None),
            patch.object(CursorScanner, "_run_cmd", return_value=None),
            patch.object(CursorScanner, "_find_madewith_trailers", return_value=[]),
        ):
            result = CursorScanner().scan(verbose=False)

        self.assertIn(("weak_identity_correlation", 0.05), result.penalties)


if __name__ == "__main__":
    unittest.main()
