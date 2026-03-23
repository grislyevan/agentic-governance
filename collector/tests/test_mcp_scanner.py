"""Tests for the MCP/A2A protocol scanner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scanner.mcp import MCPScanner, _MCP_PROCESS_PATTERNS


@pytest.fixture
def scanner():
    store = MagicMock()
    return MCPScanner(event_store=store)


class TestMCPProcessPatterns:
    def test_matches_mcp_server_prefix(self):
        assert any(p.search("mcp-server-filesystem") for p in _MCP_PROCESS_PATTERNS)

    def test_matches_uvx_mcp(self):
        assert any(p.search("uvx run mcp-server-git") for p in _MCP_PROCESS_PATTERNS)

    def test_matches_npx_mcp(self):
        assert any(p.search("npx @modelcontextprotocol/server-memory") for p in _MCP_PROCESS_PATTERNS)

    def test_no_match_on_unrelated(self):
        assert not any(p.search("node server.js") for p in _MCP_PROCESS_PATTERNS)

    def test_matches_mcp_proxy(self):
        assert any(p.search("mcp-proxy --port 3000") for p in _MCP_PROCESS_PATTERNS)


class TestClaudeDesktopConfig:
    def test_detects_claude_desktop_mcp(self, scanner, tmp_path):
        config = tmp_path / "claude_desktop_config.json"
        config.write_text(json.dumps({
            "mcpServers": {
                "filesystem": {"command": "mcp-server-filesystem"},
                "memory": {"command": "mcp-server-memory"},
            }
        }))

        with patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", [config]):
            findings = scanner._check_claude_desktop_config(verbose=False)

        assert len(findings) == 1
        assert findings[0]["vector"] == "M1-claude-desktop"
        assert "filesystem" in findings[0]["servers"]
        assert "memory" in findings[0]["servers"]

    def test_no_detection_without_mcp_servers(self, scanner, tmp_path):
        config = tmp_path / "claude_desktop_config.json"
        config.write_text(json.dumps({"theme": "dark"}))

        with patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", [config]):
            findings = scanner._check_claude_desktop_config(verbose=False)

        assert len(findings) == 0

    def test_no_detection_missing_file(self, scanner):
        with patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", [Path("/nonexistent/path.json")]):
            findings = scanner._check_claude_desktop_config(verbose=False)

        assert len(findings) == 0


class TestCursorMCPConfig:
    def test_detects_cursor_mcp(self, scanner, tmp_path):
        config = tmp_path / "mcp.json"
        config.write_text(json.dumps({
            "mcpServers": {"git": {"command": "mcp-server-git"}}
        }))

        with patch("scanner.mcp._CURSOR_MCP_PATHS", [config]):
            findings = scanner._check_cursor_mcp_config(verbose=False)

        assert len(findings) == 1
        assert findings[0]["vector"] == "M2-cursor-mcp"
        assert "git" in findings[0]["servers"]


class TestMCPProcesses:
    def test_detects_mcp_server_process(self, scanner):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "user     12345  0.0  0.1 123456  1234 ?        S    10:00   0:00 mcp-server-filesystem /home/user\n"
        )

        with patch.object(scanner, "_run_cmd", return_value=mock_result):
            findings = scanner._check_mcp_processes(verbose=False)

        assert len(findings) == 1
        assert findings[0]["vector"] == "M3-mcp-process"
        assert len(findings[0]["pids"]) == 1

    def test_no_mcp_processes(self, scanner):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            "USER       PID  %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND\n"
            "user      1000  0.0  0.1 123456  1234 ?        S    10:00   0:00 node server.js\n"
        )

        with patch.object(scanner, "_run_cmd", return_value=mock_result):
            findings = scanner._check_mcp_processes(verbose=False)

        assert len(findings) == 0


class TestProjectMCPConfigs:
    def test_detects_project_mcp_json(self, scanner, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        mcp_file = project / ".mcp.json"
        mcp_file.write_text(json.dumps({
            "mcpServers": {"db": {"command": "mcp-server-postgres"}}
        }))

        with patch("scanner.mcp._PROJECT_SEARCH_ROOTS", [tmp_path]):
            findings = scanner._check_project_mcp_configs(verbose=False)

        assert len(findings) == 1
        assert findings[0]["vector"] == "M4-project-mcp"
        assert "db" in findings[0]["servers"]

    def test_no_mcp_json_in_projects(self, scanner, tmp_path):
        project = tmp_path / "my-project"
        project.mkdir()
        (project / "package.json").write_text("{}")

        with patch("scanner.mcp._PROJECT_SEARCH_ROOTS", [tmp_path]):
            findings = scanner._check_project_mcp_configs(verbose=False)

        assert len(findings) == 0


class TestVSCodeMCPSettings:
    def test_detects_vscode_mcp(self, scanner, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({
            "mcp": {"servers": {"fetch": {"command": "mcp-server-fetch"}}}
        }))

        with patch("scanner.mcp._VSCODE_SETTINGS_PATHS", [settings]):
            findings = scanner._check_vscode_mcp_settings(verbose=False)

        assert len(findings) == 1
        assert findings[0]["vector"] == "M5-vscode-mcp"

    def test_detects_copilot_mcp(self, scanner, tmp_path):
        settings = tmp_path / "settings.json"
        settings.write_text(json.dumps({
            "github.copilot.chat.mcp.servers": {
                "context7": {"command": "npx", "args": ["-y", "@context7/mcp"]}
            }
        }))

        with patch("scanner.mcp._VSCODE_SETTINGS_PATHS", [settings]):
            findings = scanner._check_vscode_mcp_settings(verbose=False)

        assert len(findings) == 1
        assert "context7" in findings[0]["servers"]


class TestFullScan:
    def test_no_detection_clean_system(self, scanner):
        with (
            patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", []),
            patch("scanner.mcp._CURSOR_MCP_PATHS", []),
            patch("scanner.mcp._PROJECT_SEARCH_ROOTS", []),
            patch("scanner.mcp._VSCODE_SETTINGS_PATHS", []),
            patch.object(scanner, "_run_cmd", return_value=MagicMock(returncode=1, stdout="")),
        ):
            result = scanner.scan(verbose=False)

        assert not result.detected

    def test_detection_with_claude_config(self, scanner, tmp_path):
        config = tmp_path / "claude_desktop_config.json"
        config.write_text(json.dumps({
            "mcpServers": {"fs": {"command": "mcp-server-filesystem"}}
        }))

        with (
            patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", [config]),
            patch("scanner.mcp._CURSOR_MCP_PATHS", []),
            patch("scanner.mcp._PROJECT_SEARCH_ROOTS", []),
            patch("scanner.mcp._VSCODE_SETTINGS_PATHS", []),
            patch.object(scanner, "_run_cmd", return_value=MagicMock(returncode=1, stdout="")),
        ):
            result = scanner.scan(verbose=False)

        assert result.detected
        assert result.tool_name == "MCP Infrastructure"
        assert result.tool_class == "D"
        assert result.evidence_details["mcp_server_count"] == 1
        assert "fs" in result.evidence_details["mcp_server_names"]

    def test_multiple_vectors_aggregate(self, scanner, tmp_path):
        claude_cfg = tmp_path / "claude.json"
        claude_cfg.write_text(json.dumps({
            "mcpServers": {"fs": {"command": "mcp-server-fs"}}
        }))

        cursor_cfg = tmp_path / "mcp.json"
        cursor_cfg.write_text(json.dumps({
            "mcpServers": {"git": {"command": "mcp-server-git"}}
        }))

        with (
            patch("scanner.mcp._CLAUDE_DESKTOP_CONFIG_PATHS", [claude_cfg]),
            patch("scanner.mcp._CURSOR_MCP_PATHS", [cursor_cfg]),
            patch("scanner.mcp._PROJECT_SEARCH_ROOTS", []),
            patch("scanner.mcp._VSCODE_SETTINGS_PATHS", []),
            patch.object(scanner, "_run_cmd", return_value=MagicMock(returncode=1, stdout="")),
        ):
            result = scanner.scan(verbose=False)

        assert result.detected
        assert result.evidence_details["mcp_server_count"] == 2
        assert len(result.evidence_details["mcp_findings"]) == 2


class TestSafeJsonRead:
    def test_valid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text('{"key": "value"}')
        assert MCPScanner._safe_json_read(f) == {"key": "value"}

    def test_invalid_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("not json")
        assert MCPScanner._safe_json_read(f) is None

    def test_missing_file(self):
        assert MCPScanner._safe_json_read(Path("/nonexistent")) is None

    def test_non_dict_json(self, tmp_path):
        f = tmp_path / "test.json"
        f.write_text("[1, 2, 3]")
        assert MCPScanner._safe_json_read(f) is None
