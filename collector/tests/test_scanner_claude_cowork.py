"""Unit tests for ClaudeCoworkScanner."""

from __future__ import annotations

import contextlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ConnectionInfo
from scanner.claude_cowork import ClaudeCoworkScanner


class _Proc:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


class TestClaudeCoworkScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.app_support = self.home / "Claude"
        self.vm = self.app_support / "vm_bundles" / "claudevm.bundle"
        self.sessions = self.app_support / "local-agent-mode-sessions" / "s1"
        self.extensions = self.app_support / "Claude Extensions" / "schedule-agent"
        self.vm.mkdir(parents=True, exist_ok=True)
        self.sessions.mkdir(parents=True, exist_ok=True)
        self.extensions.mkdir(parents=True, exist_ok=True)
        (self.vm / "rootfs.img").write_bytes(b"x" * 1024)
        (self.vm / "vmIP").write_text("192.168.64.2")
        (self.vm / "macAddress").write_text("aa:bb:cc:dd:ee:ff")
        (self.sessions / "local_1.json").write_text(json.dumps({"emailAddress": "t@example.com", "accountName": "Tester", "remoteMcpServersConfig": [{"name": "jira"}]}))
        (self.sessions / "audit.jsonl").write_text(json.dumps({"type": "tool_use_summary", "summary": "used bash"}) + "\n")
        (self.app_support / "claude_desktop_config.json").write_text(json.dumps({"preferences": {"coworkScheduledTasksEnabled": True, "coworkWebSearchEnabled": True}}))

    def tearDown(self):
        self._tmp.cleanup()

    def _scan_with(self, run_cmd, *, connections=None):
        if connections is None:
            connections = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_APP_SUPPORT", self.app_support))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_VM_BUNDLES", self.app_support / "vm_bundles"))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_SESSIONS", self.app_support / "local-agent-mode-sessions"))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_CONFIG", self.app_support / "claude_desktop_config.json"))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_EXTENSIONS", self.app_support / "Claude Extensions"))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_APP_PATH", self.home / "Claude.app"))
            stack.enter_context(patch.object(ClaudeCoworkScanner, "_run_cmd", side_effect=run_cmd))
            stack.enter_context(patch("scanner.claude_cowork.get_connections", return_value=connections))
            stack.enter_context(patch("scanner.claude_cowork.get_process_info", return_value=None))
            return ClaudeCoworkScanner().scan(verbose=False)

    def test_positive_detection(self):
        def run_cmd(args, timeout=10):
            if args[:2] == ["pgrep", "-fl"] and "Virtualization.VirtualMachine" in args[2]:
                return _Proc(stdout="200 com.apple.Virtualization.VirtualMachine\n")
            if args[:2] == ["pgrep", "-fl"] and "Claude Helper (Plugin)" in args[2]:
                return _Proc(stdout="300 Claude Helper (Plugin)\n")
            if args[:2] == ["pgrep", "-fl"] and "Claude" in args[2]:
                return _Proc(stdout="100 /Applications/Claude.app/Contents/MacOS/Claude\n")
            return _Proc(stdout="")

        result = self._scan_with(
            run_cmd,
            connections=[ConnectionInfo(pid=100, local_addr="127.0.0.1", local_port=55000, remote_addr="1.1.1.1", remote_port=443, status="ESTABLISHED")],
        )

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.9)
        self.assertGreaterEqual(result.signals.behavior, 0.8)
        self.assertEqual(result.action_type, "approval_required")

    def test_negative_no_signal(self):
        empty = self.home / "empty"
        empty.mkdir()
        with (
            patch.object(ClaudeCoworkScanner, "_APP_SUPPORT", empty),
            patch.object(ClaudeCoworkScanner, "_VM_BUNDLES", empty / "vm"),
            patch.object(ClaudeCoworkScanner, "_SESSIONS", empty / "sessions"),
            patch.object(ClaudeCoworkScanner, "_CONFIG", empty / "config.json"),
            patch.object(ClaudeCoworkScanner, "_EXTENSIONS", empty / "ext"),
            patch.object(ClaudeCoworkScanner, "_APP_PATH", empty / "Claude.app"),
            patch.object(ClaudeCoworkScanner, "_run_cmd", return_value=_Proc(stdout="")),
            patch("scanner.claude_cowork.get_connections", return_value=[]),
            patch("scanner.claude_cowork.get_process_info", return_value=None),
        ):
            result = ClaudeCoworkScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.action_type, "none")

    def test_stale_artifact_penalty(self):
        result = self._scan_with(lambda *_a, **_k: _Proc(stdout=""))
        self.assertTrue(result.detected)
        self.assertIn(("stale_artifact_only", 0.10), result.penalties)

    def test_confidence_behavior_without_process(self):
        result = self._scan_with(lambda *_a, **_k: _Proc(stdout=""))
        self.assertEqual(result.signals.process, 0.0)
        self.assertGreater(result.signals.behavior, 0.0)


if __name__ == "__main__":
    unittest.main()
