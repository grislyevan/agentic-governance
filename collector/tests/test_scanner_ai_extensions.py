"""Unit tests for AIExtensionScanner."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from compat.types import ToolPaths
from scanner.ai_extensions import AIExtensionScanner


class TestAIExtensionScanner(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.home = Path(self._tmp.name)
        self.cursor_ext = self.home / ".cursor" / "extensions"
        self.vscode_ext = self.home / ".vscode" / "extensions"
        self.cursor_ext.mkdir(parents=True, exist_ok=True)
        self.vscode_ext.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _paths(self, tool: str) -> ToolPaths:
        if tool == "cursor":
            return ToolPaths(extensions_dir=self.cursor_ext)
        if tool == "vscode":
            return ToolPaths(extensions_dir=self.vscode_ext)
        return ToolPaths()

    def test_positive_detection(self):
        ext = self.cursor_ext / "some.ai-helper-1.0.0"
        ext.mkdir()
        (ext / "package.json").write_text('{"name":"ai-helper","displayName":"AI Helper","version":"1.0.0","keywords":["ai","llm"],"categories":["Machine Learning"],"description":"AI-powered coding helper"}')

        with patch("scanner.ai_extensions.get_tool_paths", side_effect=self._paths):
            result = AIExtensionScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertGreaterEqual(result.signals.file, 0.7)
        self.assertEqual(result.action_risk, "R1")
        self.assertEqual(result.evidence_details.get("discovered_count"), 1)

    def test_negative_no_signal(self):
        with patch("scanner.ai_extensions.get_tool_paths", side_effect=self._paths):
            result = AIExtensionScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.signals.file, 0.0)

    def test_stale_artifacts_behavior(self):
        ext = self.vscode_ext / "foo.old-ai-0.1.0"
        ext.mkdir()
        (ext / "package.json").write_text('{"displayName":"Old AI","description":"ai-assisted formatter","version":"0.1.0"}')

        with patch("scanner.ai_extensions.get_tool_paths", side_effect=self._paths):
            result = AIExtensionScanner().scan(verbose=False)

        self.assertTrue(result.detected)
        self.assertEqual(result.signals.process, 0.0)
        self.assertEqual(result.signals.behavior, 0.0)

    def test_covered_extensions_ignored(self):
        ext = self.vscode_ext / "github.copilot-chat-1.2.3"
        ext.mkdir()
        (ext / "package.json").write_text('{"displayName":"Copilot","description":"ai","version":"1.2.3"}')

        with patch("scanner.ai_extensions.get_tool_paths", side_effect=self._paths):
            result = AIExtensionScanner().scan(verbose=False)

        self.assertFalse(result.detected)
        self.assertEqual(result.evidence_details.get("discovered_count"), None)


if __name__ == "__main__":
    unittest.main()
