"""Claude Cowork detection module (Class C+ — Autonomous Executor with soft proactive capability).

Claude Cowork is a feature of Claude Desktop that runs a full Linux VM via Apple
Virtualization framework for sandboxed file operations.  It shares the Electron app
with Claude chat but adds VM-based execution, DXT extensions, MCP connectors,
scheduled tasks, and a plugin marketplace.

Key IOCs validated in LAB-RUN-014:
  - com.apple.Virtualization.VirtualMachine XPC service process
  - 10 GB vm_bundles/ directory with rootfs.img
  - Session JSONs with cleartext accountName/emailAddress
  - audit.jsonl per session with tool_use_summary events
  - coworkScheduledTasksEnabled in claude_desktop_config.json
  - DXT extensions (chrome-control, notes) with MCP servers
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from compat import find_processes, get_connections, get_process_info

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)


class ClaudeCoworkScanner(BaseScanner):
    """Detects Claude Cowork via five-layer signal model.

    Distinguishes Cowork from Claude Code CLI by checking for VM bundles,
    local-agent-mode-sessions, and cowork-specific config keys.
    """

    _APP_SUPPORT = Path.home() / "Library" / "Application Support" / "Claude"
    _VM_BUNDLES = _APP_SUPPORT / "vm_bundles"
    _SESSIONS = _APP_SUPPORT / "local-agent-mode-sessions"
    _CONFIG = _APP_SUPPORT / "claude_desktop_config.json"
    _EXTENSIONS = _APP_SUPPORT / "Claude Extensions"
    _APP_PATH = Path("/Applications/Claude.app")

    @property
    def tool_name(self) -> str:
        return "Claude Cowork"

    @property
    def tool_class(self) -> str:
        return "C"

    def scan(self, verbose: bool = False) -> ScanResult:
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

        result.signals = LayerSignals(
            process=process_strength,
            file=file_strength,
            network=network_strength,
            identity=identity_strength,
            behavior=behavior_strength,
        )

        if any(
            s > 0.0
            for s in [
                process_strength,
                file_strength,
                network_strength,
                identity_strength,
                behavior_strength,
            ]
        ):
            result.detected = True

        self._apply_class_escalation(result)
        self._apply_penalties(result)
        self._determine_action(result)
        result.tool_version = self._detect_version(verbose)

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Extract version from Info.plist or binary metadata."""
        plist = self._APP_PATH / "Contents" / "Info.plist"
        if plist.is_file():
            proc = self._run_cmd(["defaults", "read", str(plist), "CFBundleVersion"])
            if proc and proc.returncode == 0 and proc.stdout.strip():
                ver = proc.stdout.strip()
                self._log(f"Version from Info.plist: {ver}", verbose)
                return ver
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning process layer...", verbose)
        strength = 0.0
        own_pid = str(os.getpid())
        own_ppid = str(os.getppid())

        proc = self._run_cmd(["pgrep", "-fl", "Claude"])
        if proc and proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.strip().splitlines()
            claude_pids: list[str] = []
            for line in lines:
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid, cmdline = parts
                if pid in (own_pid, own_ppid):
                    continue
                if "pgrep" in cmdline.lower():
                    continue
                if "Claude.app" in cmdline and "collector" not in cmdline.lower():
                    claude_pids.append(pid)
                    result.evidence_details.setdefault("process_entries", []).append(
                        {"pid": pid, "cmdline": cmdline}
                    )

            if claude_pids:
                strength = 0.60
                self._log(f"Found Claude Desktop process(es): {claude_pids}", verbose)

        vm_proc = self._run_cmd(["pgrep", "-fl", "Virtualization.VirtualMachine"])
        if vm_proc and vm_proc.returncode == 0 and vm_proc.stdout.strip():
            strength = max(strength, 0.85)
            result.evidence_details["vm_process"] = True
            self._log("Found Virtualization.VirtualMachine XPC service", verbose)

        plugin_proc = self._run_cmd(["pgrep", "-fl", "Claude Helper (Plugin)"])
        if plugin_proc and plugin_proc.returncode == 0 and plugin_proc.stdout.strip():
            strength = max(strength, 0.70)
            result.evidence_details["plugin_helpers"] = True
            self._log("Found Claude Helper (Plugin) processes — DXT hosts", verbose)

        if strength >= 0.60:
            binary = self._APP_PATH / "Contents" / "MacOS" / "Claude"
            if binary.is_file():
                hash_proc = self._run_cmd(["shasum", "-a", "256", str(binary)])
                if hash_proc and hash_proc.returncode == 0:
                    sha = hash_proc.stdout.strip().split()[0]
                    result.evidence_details["binary_sha256"] = sha
                    self._log(f"Binary hash: {sha}", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        if self._VM_BUNDLES.is_dir():
            strength = 0.90
            result.evidence_details["vm_bundles_present"] = True
            rootfs = self._VM_BUNDLES / "claudevm.bundle" / "rootfs.img"
            if rootfs.is_file():
                size_gb = rootfs.stat().st_size / (1024 ** 3)
                result.evidence_details["rootfs_size_gb"] = round(size_gb, 1)
                self._log(f"VM rootfs.img: {size_gb:.1f} GB", verbose)

        if self._SESSIONS.is_dir():
            strength = max(strength, 0.75)
            session_jsons = list(self._SESSIONS.rglob("local_*.json"))
            result.evidence_details["session_count"] = len(session_jsons)
            self._log(f"Found {len(session_jsons)} session JSON files", verbose)

            audit_logs = list(self._SESSIONS.rglob("audit.jsonl"))
            result.evidence_details["audit_log_count"] = len(audit_logs)

        if self._CONFIG.is_file():
            try:
                config = json.loads(self._CONFIG.read_text())
                prefs = config.get("preferences", {})
                cowork_keys = {
                    k: v
                    for k, v in prefs.items()
                    if "cowork" in k.lower() or "localAgentMode" in k
                }
                if cowork_keys:
                    strength = max(strength, 0.80)
                    result.evidence_details["cowork_config"] = cowork_keys
                    self._log(f"Cowork config keys: {cowork_keys}", verbose)
            except (json.JSONDecodeError, PermissionError, OSError) as exc:
                logger.debug("Could not read cowork config from %s: %s", self._CONFIG, exc)

        if self._EXTENSIONS.is_dir():
            extensions = [
                d.name for d in self._EXTENSIONS.iterdir() if d.is_dir()
            ]
            if extensions:
                result.evidence_details["dxt_extensions"] = extensions
                self._log(f"DXT extensions: {extensions}", verbose)
            # Schedule-type skill: extension or skill dir with "schedule" in name (LAB-RUN-015)
            schedule_related = [
                p.name for p in self._EXTENSIONS.rglob("*")
                if "schedule" in p.name.lower() and (p.is_dir() or p.suffix in (".json", ".py", ".md", ".yaml", ".yml"))
            ]
            if schedule_related:
                result.evidence_details["schedule_skill_artifacts"] = schedule_related[:20]
                strength = max(strength, 0.55)
                self._log(f"Schedule-related artifacts: {schedule_related[:5]}", verbose)

        skills_dirs = list(self._SESSIONS.rglob("skills-plugin")) if self._SESSIONS.is_dir() else []
        if skills_dirs:
            result.evidence_details["skills_plugin_present"] = True

        marketplace_dirs = list(self._SESSIONS.rglob("knowledge-work-plugins")) if self._SESSIONS.is_dir() else []
        if marketplace_dirs:
            result.evidence_details["marketplace_present"] = True

        return strength

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        conns = get_connections()
        for c in conns:
            proc = get_process_info(c.pid) if c.pid else None
            line = f"{c.pid or ''} {proc.cmdline if proc else ''} {c.remote_addr or ''}:{c.remote_port or ''} {c.status}"
            if "claude" in line.lower():
                strength = max(strength, 0.65)
                result.evidence_details.setdefault("network_connections", []).append(line)

        vm_ip_path = self._VM_BUNDLES / "claudevm.bundle" / "vmIP"
        if vm_ip_path.is_file():
            try:
                vm_ip = vm_ip_path.read_text().strip()
                result.evidence_details["vm_ip"] = vm_ip
                self._log(f"VM IP: {vm_ip}", verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not read VM IP from %s: %s", vm_ip_path, exc)

        vm_mac_path = self._VM_BUNDLES / "claudevm.bundle" / "macAddress"
        if vm_mac_path.is_file():
            try:
                vm_mac = vm_mac_path.read_text().strip()
                result.evidence_details["vm_mac"] = vm_mac
                strength = max(strength, 0.50)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not read VM MAC from %s: %s", vm_mac_path, exc)

        if self._CONFIG.is_file():
            try:
                config = json.loads(self._CONFIG.read_text())
                prefs = config.get("preferences", {})
                if prefs.get("coworkWebSearchEnabled"):
                    result.evidence_details["web_search_enabled"] = True
            except (json.JSONDecodeError, PermissionError, OSError) as exc:
                logger.debug("Could not read config for web search preference: %s", exc)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        if self._APP_PATH.is_dir():
            codesign = self._run_cmd(["codesign", "-dvvv", str(self._APP_PATH)])
            if codesign and codesign.returncode == 0:
                output = codesign.stderr or ""
                if "Anthropic" in output:
                    strength = 0.60
                    if "Q6L2SF6YDW" in output:
                        result.evidence_details["code_signing_team"] = "Q6L2SF6YDW"

        if self._SESSIONS.is_dir():
            session_jsons = sorted(
                self._SESSIONS.rglob("local_*.json"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            for sjson in session_jsons[:3]:
                try:
                    data = json.loads(sjson.read_text())
                    email = data.get("emailAddress")
                    name = data.get("accountName")
                    if email:
                        strength = max(strength, 0.90)
                        result.evidence_details["account_email"] = email
                        result.evidence_details["account_name"] = name
                        self._log(f"Identity: {name} <{email}>", verbose)
                        break
                except (json.JSONDecodeError, PermissionError, OSError):
                    continue

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if self._SESSIONS.is_dir():
            audit_logs = sorted(
                self._SESSIONS.rglob("audit.jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for audit_path in audit_logs[:5]:
                try:
                    events = []
                    with open(audit_path) as f:
                        for line in f:
                            try:
                                events.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue

                    tool_use_summaries = [
                        e.get("summary", "")
                        for e in events
                        if e.get("type") == "tool_use_summary"
                    ]
                    if tool_use_summaries:
                        strength = max(strength, 0.80)
                        result.evidence_details.setdefault("tool_use_summaries", []).extend(
                            tool_use_summaries[:10]
                        )
                        self._log(
                            f"Found {len(tool_use_summaries)} tool_use_summary events in {audit_path.name}",
                            verbose,
                        )
                except (PermissionError, OSError):
                    continue

        if self._CONFIG.is_file():
            try:
                config = json.loads(self._CONFIG.read_text())
                prefs = config.get("preferences", {})
                if prefs.get("coworkScheduledTasksEnabled"):
                    strength = max(strength, 0.70)
                    result.evidence_details["scheduled_tasks_enabled"] = True
                    self._log("Scheduled tasks enabled", verbose)
            except (json.JSONDecodeError, PermissionError, OSError) as exc:
                logger.debug("Could not read config for scheduled tasks preference: %s", exc)

        session_jsons = sorted(
            self._SESSIONS.rglob("local_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ) if self._SESSIONS.is_dir() else []
        for sjson in session_jsons[:3]:
            try:
                data = json.loads(sjson.read_text())
                mcp_servers = data.get("remoteMcpServersConfig", [])
                if mcp_servers:
                    strength = max(strength, 0.75)
                    result.evidence_details["mcp_servers"] = [
                        s.get("name") for s in mcp_servers
                    ]
                    self._log(
                        f"MCP connectors: {[s.get('name') for s in mcp_servers]}",
                        verbose,
                    )
                    break
            except (json.JSONDecodeError, PermissionError, OSError):
                continue

        return strength

    def _apply_class_escalation(self, result: ScanResult) -> None:
        """Escalate to C+ if scheduled tasks or self-modification detected."""
        details = result.evidence_details
        if (
            details.get("scheduled_tasks_enabled")
            or details.get("skills_plugin_present")
            or details.get("schedule_skill_artifacts")
        ):
            result.action_risk = "R2"
            result.action_summary += " Class D-adjacent: scheduled tasks or self-modification capability detected."

    def _apply_penalties(self, result: ScanResult) -> None:
        if result.signals.process == 0.0 and (result.signals.file > 0.0 or result.signals.identity > 0.0):
            result.penalties.append(("stale_artifact_only", 0.10))

    def _determine_action(self, result: ScanResult) -> None:
        if not result.detected:
            result.action_type = "none"
            result.action_summary = "No Claude Cowork signals detected."
            return

        confidence = sum(
            [
                result.signals.process,
                result.signals.file,
                result.signals.network,
                result.signals.identity,
                result.signals.behavior,
            ]
        ) / 5.0

        if confidence >= 0.75:
            result.action_type = "approval_required"
            result.action_summary = (
                f"Claude Cowork detected with high confidence. "
                f"Class C+ tool with VM-based execution."
                + (result.action_summary or "")
            )
        elif confidence >= 0.45:
            result.action_type = "warn"
            result.action_summary = (
                f"Claude Cowork signals detected (medium confidence). "
                f"Review session data and MCP connectors."
                + (result.action_summary or "")
            )
        else:
            result.action_type = "observe"
            result.action_summary = (
                f"Weak Claude Cowork signals. May be residual files only."
                + (result.action_summary or "")
            )
