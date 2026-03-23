"""Model Context Protocol (MCP) and Agent-to-Agent (A2A) scanner.

Detects the presence of MCP servers, MCP client configurations,
and related agentic protocol infrastructure on the endpoint:

  M1: Claude Desktop MCP config (claude_desktop_config.json with mcpServers)
  M2: Cursor MCP config (.cursor/mcp.json or .cursorrc with MCP entries)
  M3: MCP server processes (mcp-server-*, uvx mcp, npx mcp)
  M4: .mcp.json project-level config files
  M5: VS Code / Copilot MCP settings

MCP adoption signals are relevant for AI governance because MCP servers
grant AI tools access to local resources (files, databases, APIs) that
may fall outside standard security controls.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from scanner.base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)

_MCP_PROCESS_PATTERNS = [
    re.compile(r"mcp-server", re.IGNORECASE),
    re.compile(r"mcp[-_]proxy", re.IGNORECASE),
    re.compile(r"\buvx\b.*\bmcp\b", re.IGNORECASE),
    re.compile(r"\bnpx\b.*\bmcp\b", re.IGNORECASE),
    re.compile(r"\bnpx\b.*@modelcontextprotocol", re.IGNORECASE),
    re.compile(r"modelcontextprotocol", re.IGNORECASE),
]

_CLAUDE_DESKTOP_CONFIG_PATHS = [
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json",
    Path.home() / ".config" / "Claude" / "claude_desktop_config.json",
    Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
]

_CURSOR_MCP_PATHS = [
    Path.home() / ".cursor" / "mcp.json",
]

_VSCODE_SETTINGS_PATHS = [
    Path.home() / ".vscode" / "settings.json",
    Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json",
    Path.home() / ".config" / "Code" / "User" / "settings.json",
    Path.home() / "AppData" / "Roaming" / "Code" / "User" / "settings.json",
]

_PROJECT_SEARCH_ROOTS = [
    Path.home(),
    Path.home() / "Documents",
    Path.home() / "code",
    Path.home() / "projects",
    Path.home() / "src",
    Path.home() / "dev",
    Path.home() / "repos",
    Path.home() / "workspace",
]

MAX_PROJECTS_TO_SCAN = 50


class MCPScanner(BaseScanner):
    """Detect Model Context Protocol infrastructure on the endpoint."""

    @property
    def tool_name(self) -> str:
        return "MCP Infrastructure"

    @property
    def tool_class(self) -> str:
        return "D"

    def scan(self, verbose: bool = False) -> ScanResult:
        result = ScanResult(
            detected=False,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
        )
        findings: list[dict[str, Any]] = []

        self._log("Scanning for MCP/A2A protocol infrastructure...", verbose)

        findings.extend(self._check_claude_desktop_config(verbose))
        findings.extend(self._check_cursor_mcp_config(verbose))
        findings.extend(self._check_mcp_processes(verbose))
        findings.extend(self._check_project_mcp_configs(verbose))
        findings.extend(self._check_vscode_mcp_settings(verbose))

        if findings:
            result.detected = True
            server_names = set()
            for f in findings:
                for s in f.get("servers", []):
                    server_names.add(s)

            result.evidence_details["mcp_findings"] = findings
            result.evidence_details["mcp_server_count"] = len(server_names)
            result.evidence_details["mcp_server_names"] = sorted(server_names)
            result.signals.file = 0.7
            result.signals.process = 0.5 if any(
                f["vector"].startswith("M3") for f in findings
            ) else 0.2
            result.signals.behavior = 0.4
            result.action_summary = (
                f"MCP: {len(findings)} indicator(s), "
                f"{len(server_names)} server(s) configured"
            )
            self._log(
                f"Found {len(findings)} MCP indicator(s) with "
                f"{len(server_names)} unique server(s)",
                verbose,
            )
        else:
            self._log("No MCP infrastructure found.", verbose)

        return result

    def _check_claude_desktop_config(self, verbose: bool) -> list[dict[str, Any]]:
        """M1: Check Claude Desktop config for MCP servers."""
        findings = []
        for config_path in _CLAUDE_DESKTOP_CONFIG_PATHS:
            if not config_path.is_file():
                continue
            data = self._safe_json_read(config_path)
            if not data:
                continue
            servers = data.get("mcpServers", {})
            if not servers:
                continue
            findings.append({
                "vector": "M1-claude-desktop",
                "description": f"Claude Desktop MCP config with {len(servers)} server(s)",
                "path": str(config_path),
                "servers": list(servers.keys()),
            })
            self._log(f"  M1: Claude Desktop MCP: {list(servers.keys())}", verbose)
        return findings

    def _check_cursor_mcp_config(self, verbose: bool) -> list[dict[str, Any]]:
        """M2: Check Cursor MCP configuration."""
        findings = []
        for config_path in _CURSOR_MCP_PATHS:
            if not config_path.is_file():
                continue
            data = self._safe_json_read(config_path)
            if not data:
                continue
            servers = data.get("mcpServers", {})
            if not servers:
                continue
            findings.append({
                "vector": "M2-cursor-mcp",
                "description": f"Cursor MCP config with {len(servers)} server(s)",
                "path": str(config_path),
                "servers": list(servers.keys()),
            })
            self._log(f"  M2: Cursor MCP: {list(servers.keys())}", verbose)
        return findings

    def _check_mcp_processes(self, verbose: bool) -> list[dict[str, Any]]:
        """M3: Check for running MCP server processes."""
        findings = []
        ps_result = self._run_cmd(["ps", "aux"])
        if not ps_result or ps_result.returncode != 0:
            return findings

        matched_pids: set[str] = set()
        servers_found: list[str] = []

        for line in ps_result.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            cmd = parts[10]
            pid = parts[1]
            for pattern in _MCP_PROCESS_PATTERNS:
                if pattern.search(cmd) and pid not in matched_pids:
                    matched_pids.add(pid)
                    name_match = re.search(r"mcp-server-(\S+)", cmd, re.IGNORECASE)
                    server_name = name_match.group(1) if name_match else cmd.split()[0]
                    servers_found.append(server_name)
                    self._log(f"  M3: MCP process PID {pid}: {cmd[:80]}", verbose)
                    break

        if matched_pids:
            findings.append({
                "vector": "M3-mcp-process",
                "description": f"{len(matched_pids)} MCP server process(es) running",
                "servers": servers_found,
                "pids": sorted(matched_pids),
            })
        return findings

    def _check_project_mcp_configs(self, verbose: bool) -> list[dict[str, Any]]:
        """M4: Scan project directories for .mcp.json files."""
        findings = []
        scanned = 0

        for root in _PROJECT_SEARCH_ROOTS:
            if not root.is_dir():
                continue
            try:
                for entry in root.iterdir():
                    if not entry.is_dir():
                        continue
                    mcp_file = entry / ".mcp.json"
                    if mcp_file.is_file():
                        data = self._safe_json_read(mcp_file)
                        servers = {}
                        if data:
                            servers = data.get("mcpServers", data.get("servers", {}))
                        findings.append({
                            "vector": "M4-project-mcp",
                            "description": f"Project MCP config in {entry.name}",
                            "path": str(mcp_file),
                            "servers": list(servers.keys()) if servers else [],
                        })
                        self._log(f"  M4: Project MCP: {mcp_file}", verbose)
                    scanned += 1
                    if scanned >= MAX_PROJECTS_TO_SCAN:
                        break
            except PermissionError:
                continue
            if scanned >= MAX_PROJECTS_TO_SCAN:
                break

        return findings

    def _check_vscode_mcp_settings(self, verbose: bool) -> list[dict[str, Any]]:
        """M5: Check VS Code settings for MCP server configuration."""
        findings = []
        for settings_path in _VSCODE_SETTINGS_PATHS:
            if not settings_path.is_file():
                continue
            data = self._safe_json_read(settings_path)
            if not data:
                continue
            mcp_servers = data.get("mcp", {}).get("servers", {})
            if not mcp_servers:
                mcp_servers = data.get("github.copilot.chat.mcp.servers", {})
            if not mcp_servers:
                continue
            findings.append({
                "vector": "M5-vscode-mcp",
                "description": f"VS Code MCP config with {len(mcp_servers)} server(s)",
                "path": str(settings_path),
                "servers": list(mcp_servers.keys()),
            })
            self._log(f"  M5: VS Code MCP: {list(mcp_servers.keys())}", verbose)
        return findings

    @staticmethod
    def _safe_json_read(path: Path, max_size: int = 256 * 1024) -> dict | None:
        """Read and parse a JSON file, returning None on error."""
        try:
            if path.stat().st_size > max_size:
                return None
            content = path.read_text(errors="replace")
            data = json.loads(content)
            return data if isinstance(data, dict) else None
        except (OSError, PermissionError, json.JSONDecodeError, ValueError):
            return None
