"""Cline detection module (Class A/C — IDE-embedded Autonomous Assistant).

Cline (formerly Claude Dev, VS Code extension ID: saoudrizwan.claude-dev) is an
autonomous coding agent embedded in VS Code / Cursor. It is Class A when in chat
mode and escalates to Class C when tool-calling is active (file writes, shell
execution, browser automation). Detection anchors (priority order):
  1. Extension directory: saoudrizwan.claude-dev-* in VS Code / Cursor extensions
  2. Task history in globalStorage (primary evidence of agentic activity)
  3. API conversation log in per-task directories
  4. Extension host process with API traffic
  5. IDE process + TLS connections from extension host
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)
HOME = Path.home()

VSCODE_EXT_BASE = HOME / "Library" / "Application Support" / "Code" / "User"
CURSOR_EXT_BASE = HOME / "Library" / "Application Support" / "Cursor" / "User"

EXTENSION_ID = "saoudrizwan.claude-dev"
EXTENSION_GLOB_PREFIX = "saoudrizwan.claude-dev-"


class ClineScanner(BaseScanner):
    """Detects Cline VS Code extension via five-layer signal model."""

    _dynamic_tool_class: str = "A"

    @property
    def tool_name(self) -> str:
        return "Cline"

    @property
    def tool_class(self) -> str:
        return self._dynamic_tool_class

    def scan(self, verbose: bool = False) -> ScanResult:
        self._dynamic_tool_class = "A"
        result = ScanResult(
            detected=False,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
        )

        process_strength = self._scan_process(result, verbose)
        file_strength = self._scan_file(result, verbose)
        network_strength = self._scan_network(result, verbose)
        identity_strength = self._scan_identity(result, verbose)
        behavior_strength = self._scan_behavior(result, verbose)

        result.tool_class = self._dynamic_tool_class

        result.signals = LayerSignals(
            process=process_strength,
            file=file_strength,
            network=network_strength,
            identity=identity_strength,
            behavior=behavior_strength,
        )

        if any(s > 0.0 for s in [process_strength, file_strength, network_strength,
                                   identity_strength, behavior_strength]):
            result.detected = True

        self._apply_penalties(result)
        self._determine_action(result)
        result.tool_version = self._detect_version(verbose)

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Detect Cline extension version from extension manifest."""
        for ext_dir in self._all_extension_dirs():
            if not ext_dir.is_dir():
                continue
            try:
                for entry in ext_dir.iterdir():
                    if not entry.is_dir() or not entry.name.startswith(EXTENSION_GLOB_PREFIX):
                        continue
                    pkg = entry / "package.json"
                    if pkg.is_file():
                        try:
                            data = json.loads(pkg.read_text())
                            version = data.get("version")
                            if version:
                                self._log(f"Version from manifest: {version}", verbose)
                                return str(version)
                        except (json.JSONDecodeError, OSError) as exc:
                            logger.debug("Could not read Cline package.json %s: %s", pkg, exc)
            except (PermissionError, OSError):
                continue
        return None

    def _all_extension_dirs(self) -> list[Path]:
        return [
            VSCODE_EXT_BASE / "extensions",
            CURSOR_EXT_BASE / "extensions",
            HOME / ".vscode" / "extensions",
            HOME / ".cursor" / "extensions",
        ]

    def _all_storage_dirs(self) -> list[tuple[str, Path]]:
        return [
            ("VSCode", VSCODE_EXT_BASE / "globalStorage" / EXTENSION_ID),
            ("Cursor", CURSOR_EXT_BASE / "globalStorage" / EXTENSION_ID),
        ]

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for VS Code / Cursor extension host processes."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        for ide_name in ("Code", "Cursor"):
            proc = self._run_cmd(["pgrep", "-fl", ide_name])
            if not (proc and proc.returncode == 0 and proc.stdout.strip()):
                continue
            for line in proc.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid, cmdline = parts
                if "pgrep" in cmdline.lower() or "collector" in cmdline.lower():
                    continue
                if "extensionHost" in cmdline or "extension-host" in cmdline:
                    result.evidence_details.setdefault("extension_hosts", []).append({
                        "ide": ide_name, "pid": pid,
                    })
                    strength = max(strength, 0.30)
                    self._log(f"  {ide_name} extension host PID {pid}", verbose)

        if strength > 0:
            self._log(
                f"  {len(result.evidence_details.get('extension_hosts', []))} extension host(s) found",
                verbose,
            )
        else:
            self._log("  No extension host found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for extension install and task history in globalStorage."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        # Check extension manifests
        ext_installs: list[dict[str, str]] = []
        for ext_dir in self._all_extension_dirs():
            if not ext_dir.is_dir():
                continue
            try:
                for entry in ext_dir.iterdir():
                    if entry.is_dir() and entry.name.startswith(EXTENSION_GLOB_PREFIX):
                        ide_label = "Cursor" if "Cursor" in str(ext_dir) else "VSCode"
                        ext_installs.append({"ide": ide_label, "dir": entry.name})
                        self._log(f"  Extension: {entry.name} ({ide_label})", verbose)
            except (PermissionError, OSError):
                continue

        if ext_installs:
            strength = 0.65
            result.evidence_details["extension_installs"] = ext_installs

        # Check globalStorage for task history (primary agentic evidence)
        for ide_label, storage_dir in self._all_storage_dirs():
            if not storage_dir.is_dir():
                continue
            result.evidence_details.setdefault("global_storage_dirs", []).append({
                "ide": ide_label, "path": str(storage_dir),
            })
            strength = max(strength, 0.75)
            self._log(f"  GlobalStorage found ({ide_label}): {storage_dir}", verbose)

            self._inspect_storage(storage_dir, ide_label, result, verbose)

        return strength

    def _inspect_storage(
        self,
        storage_dir: Path,
        ide_label: str,
        result: ScanResult,
        verbose: bool,
    ) -> None:
        """Inspect Cline's globalStorage directory for task history and tool-call config."""
        tasks_dir = storage_dir / "tasks"
        if tasks_dir.is_dir():
            try:
                task_dirs = [d for d in tasks_dir.iterdir() if d.is_dir()]
                result.evidence_details["task_count"] = len(task_dirs)
                self._log(f"  {len(task_dirs)} task(s) in {ide_label} task history", verbose)

                # Check most recent task for tool-call evidence
                if task_dirs:
                    sorted_tasks = sorted(
                        task_dirs,
                        key=lambda d: d.stat().st_mtime,
                        reverse=True,
                    )
                    self._inspect_task(sorted_tasks[0], result, verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not inspect Cline tasks dir %s: %s", tasks_dir, exc)

        # Check api_conversation_history (indicates actual LLM usage)
        for api_log in storage_dir.rglob("api_conversation_history.json"):
            try:
                data = json.loads(api_log.read_text())
                if isinstance(data, list) and len(data) > 0:
                    result.evidence_details["api_conversation_count"] = len(data)
                    self._log(f"  API conversation log: {len(data)} messages", verbose)
                break
            except (json.JSONDecodeError, OSError) as exc:
                logger.debug("Could not read Cline api_conversation_history.json %s: %s", api_log, exc)

    def _inspect_task(self, task_dir: Path, result: ScanResult, verbose: bool) -> None:
        """Examine a Cline task directory for tool-call activity."""
        try:
            ui_messages = task_dir / "ui_messages.json"
            if ui_messages.is_file():
                data = json.loads(ui_messages.read_text())
                if isinstance(data, list):
                    tool_calls = [
                        m for m in data
                        if isinstance(m, dict) and m.get("type") in (
                            "tool_use", "tool", "tool_call", "ask",
                        )
                    ]
                    if tool_calls:
                        result.evidence_details["tool_calls_in_last_task"] = len(tool_calls)
                        self._dynamic_tool_class = "C"
                        self._log(
                            f"  {len(tool_calls)} tool call(s) in latest task → Class C",
                            verbose,
                        )
                    # Check for file writes and shell executions
                    write_ops = [
                        m for m in data
                        if isinstance(m, dict) and str(m.get("type", "")).lower()
                        in ("write_to_file", "execute_command", "browser_action")
                    ]
                    if write_ops:
                        result.evidence_details["write_ops_in_last_task"] = len(write_ops)
                        self._dynamic_tool_class = "C"
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Could not read Cline ui_messages.json %s: %s", ui_messages, exc)

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for API traffic from extension host PIDs."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        ext_host_pids = {
            e["pid"] for e in result.evidence_details.get("extension_hosts", [])
        }
        if not ext_host_pids:
            return strength

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if not (lsof and lsof.returncode == 0):
            return strength

        tls_conns: list[str] = []
        llm_conns: list[str] = []
        llm_patterns = ["api.openai.com", "api.anthropic.com", ":11434", ":1234"]

        for line in lsof.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] not in ext_host_pids:
                continue
            if ":443" in line and "ESTABLISHED" in line:
                tls_conns.append(line.strip())
            for pattern in llm_patterns:
                if pattern in line and "ESTABLISHED" in line:
                    llm_conns.append(line.strip())
                    break

        if llm_conns:
            strength = 0.55
            result.evidence_details["llm_connections"] = llm_conns[:5]
            self._log(f"  {len(llm_conns)} LLM endpoint connection(s) from extension host", verbose)
        elif tls_conns:
            strength = 0.35
            result.evidence_details["tls_connection_count"] = len(tls_conns)
            self._log(f"  {len(tls_conns)} TLS connection(s) from extension host", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user and API key presence."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        import getpass
        result.evidence_details["identity_user"] = getpass.getuser()
        strength = 0.25

        for key_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            if os.environ.get(key_name):
                result.evidence_details.setdefault("api_keys_present", []).append(key_name)
                strength = max(strength, 0.45)
                self._log(f"  API key in env: {key_name}", verbose)

        git_email = self._run_cmd(["git", "config", "--global", "user.email"])
        if git_email and git_email.returncode == 0 and git_email.stdout.strip():
            result.evidence_details["git_user_email"] = git_email.stdout.strip()
            strength = max(strength, 0.35)

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for tool-call activity and recent task history."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        task_count = result.evidence_details.get("task_count", 0)
        tool_calls = result.evidence_details.get("tool_calls_in_last_task", 0)
        write_ops = result.evidence_details.get("write_ops_in_last_task", 0)

        if write_ops > 0:
            strength = 0.85
            self._dynamic_tool_class = "C"
            self._log(f"  {write_ops} file write / shell exec / browser op(s) in last task → Class C", verbose)
        elif tool_calls > 0:
            strength = 0.75
            self._dynamic_tool_class = "C"
            self._log(f"  {tool_calls} tool call(s) in last task → Class C", verbose)
        elif task_count > 0:
            strength = 0.55
            self._log(f"  {task_count} task(s) in history (no active tool calls)", verbose)

        # Check recency of task files
        now = time.time()
        recent_threshold = 3600
        for ide_label, storage_dir in self._all_storage_dirs():
            if not (storage_dir / "tasks").is_dir():
                continue
            try:
                for task_dir in (storage_dir / "tasks").iterdir():
                    if task_dir.is_dir() and (now - task_dir.stat().st_mtime) < recent_threshold:
                        result.evidence_details["recent_task"] = True
                        strength = max(strength, 0.70)
                        self._log("  Recent Cline task (modified within 1h)", verbose)
                        break
            except (PermissionError, OSError) as exc:
                logger.debug("Could not iterate Cline task dirs for recency check: %s", exc)

        if result.evidence_details.get("api_conversation_count", 0) > 10:
            strength = max(strength, 0.65)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        self._penalize_stale_artifacts(result, amount=0.05)
        self._penalize_weak_identity(result, threshold=0.4, amount=0.05)

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []
        tool_class = self._dynamic_tool_class

        if result.evidence_details.get("write_ops_in_last_task"):
            count = result.evidence_details["write_ops_in_last_task"]
            summaries.append(f"Cline Class C: {count} write/exec/browser op(s) in last task")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("tool_calls_in_last_task"):
            count = result.evidence_details["tool_calls_in_last_task"]
            summaries.append(f"Cline Class C: {count} tool call(s) in last task")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("task_count", 0) > 0:
            count = result.evidence_details["task_count"]
            summaries.append(f"Cline ({tool_class}): {count} task(s) in history")
            result.action_type = "read"
            result.action_risk = "R1"
        elif result.evidence_details.get("extension_installs"):
            summaries.append(f"Cline extension installed ({tool_class})")
            result.action_type = "read"
            result.action_risk = "R1"

        installs = result.evidence_details.get("extension_installs", [])
        if installs:
            ides = list({i["ide"] for i in installs})
            summaries.append(f"IDEs: {', '.join(ides)}")

        if result.evidence_details.get("api_keys_present"):
            keys = result.evidence_details["api_keys_present"]
            summaries.append(f"API keys in env: {', '.join(keys)}")

        if result.evidence_details.get("llm_connections"):
            summaries.append("active LLM API connection from extension host")

        result.action_summary = "; ".join(summaries) if summaries else "No Cline signals detected"
