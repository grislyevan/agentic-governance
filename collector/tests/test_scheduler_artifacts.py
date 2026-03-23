"""Tests for scheduler artifact discovery (cron/LaunchAgent)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from scanner.scheduler_artifacts import (
    get_scheduler_entries,
    get_scheduler_evidence_by_tool,
    _match_binary,
    BINARY_TO_TOOL,
)


class TestMatchBinary:
    """Test binary pattern matching in command strings."""

    def test_claude_code_match(self):
        assert _match_binary("/usr/local/bin/claude run") == ("Claude Code", "C")
        assert _match_binary("claude --version") == ("Claude Code", "C")

    def test_aider_match(self):
        assert _match_binary("aider --model gpt-4 file.py") == ("Aider", "C")

    def test_cursor_match(self):
        assert _match_binary("/Applications/Cursor.app/Contents/MacOS/Cursor") == ("Cursor", "A")

    def test_ollama_match(self):
        assert _match_binary("ollama run llama2") == ("Ollama", "B")

    def test_continue_no_false_positive_on_continued(self):
        # "continued" should not match "continue" (word boundary)
        assert _match_binary("echo continued") is None

    def test_open_interpreter_match(self):
        assert _match_binary("python -m interpreter") == ("Open Interpreter", "C")

    def test_no_match_generic(self):
        assert _match_binary("ls -la") is None
        assert _match_binary("python script.py") is None


class TestGetSchedulerEvidenceByTool:
    """Test that get_scheduler_evidence_by_tool returns dict keyed by tool_name."""

    @pytest.fixture
    def mock_empty_scheduler(self):
        with patch(
            "scanner.scheduler_artifacts.get_scheduler_entries",
            return_value=[],
        ):
            yield

    def test_returns_dict(self, mock_empty_scheduler):
        out = get_scheduler_evidence_by_tool()
        assert isinstance(out, dict)
        assert out == {}

    @pytest.fixture
    def mock_one_entry(self):
        with patch(
            "scanner.scheduler_artifacts.get_scheduler_entries",
            return_value=[
                {"source": "crontab", "path": "crontab (user)", "command": "0 2 * * * claude run", "tool_name": "Claude Code", "tool_class": "C"},
            ],
        ):
            yield

    def test_groups_by_tool_name(self, mock_one_entry):
        out = get_scheduler_evidence_by_tool()
        assert "Claude Code" in out
        assert len(out["Claude Code"]) == 1
        assert out["Claude Code"][0]["source"] == "crontab"


class TestGetSchedulerEntriesIntegration:
    """Integration-style tests with mocked subprocess and paths."""

    @patch("scanner.scheduler_artifacts._get_user_crontab", return_value=[])
    @patch("scanner.scheduler_artifacts._read_cron_dir", return_value=[])
    @patch("scanner.scheduler_artifacts._get_launch_agent_entries", return_value=[])
    def test_returns_only_matching_entries(self, mock_launch, mock_cron, mock_crontab):
        mock_crontab.return_value = [
            {"source": "crontab", "path": "crontab (user)", "command": "0 2 * * * /usr/bin/true"},
            {"source": "crontab", "path": "crontab (user)", "command": "0 3 * * * aider --yes"},
        ]
        entries = get_scheduler_entries()
        assert len(entries) == 1
        assert entries[0]["tool_name"] == "Aider"
        assert entries[0]["tool_class"] == "C"
