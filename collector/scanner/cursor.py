"""Cursor IDE detection module (Class A->C -- Assistive to Autonomous Executor).

Cursor is an Electron-based IDE (VS Code fork) that runs Class A assistive features
by default and escalates to Class C when the agent-exec extension host spawns shell
processes. The ``extension-host (agent-exec)`` process is the binary Class C indicator.
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from compat import (
    find_processes,
    get_app_version,
    get_child_pids,
    get_connections,
    get_process_info,
    get_tool_paths,
    verify_code_signature,
    ToolPaths,
)

from .base import BaseScanner, LayerSignals, ScanResult

MAX_REPOS_TO_SCAN = 10

_SHELL_NAMES = re.compile(r"(bash|zsh|sh|powershell|pwsh|cmd)(\b|\.exe)", re.IGNORECASE)


class CursorScanner(BaseScanner):
    """Detects Cursor IDE presence and agent-mode escalation via five-layer signal model."""

    _dynamic_tool_class: str = "A"

    def __init__(self) -> None:
        self._paths: ToolPaths = get_tool_paths("cursor")

    @property
    def tool_name(self) -> str:
        return "Cursor"

    @property
    def tool_class(self) -> str:
        return self._dynamic_tool_class

    def scan(self, verbose: bool = False) -> ScanResult:
        self._dynamic_tool_class = "A"
        self._paths = get_tool_paths("cursor")
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
        """Detect Cursor app version via platform abstraction."""
        install_dir = self._paths.install_dir
        if install_dir is None:
            return None
        version = get_app_version(install_dir)
        if version:
            self._log(f"Version: {version}", verbose)
        return version

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for Cursor Electron process tree and agent-exec extension host."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        procs = find_processes("Cursor")
        procs = [
            p for p in procs
            if "collector" not in p.cmdline.lower()
            and re.search(r"Cursor", p.cmdline)
        ]

        if not procs:
            self._log("No Cursor process found", verbose)
            return strength

        cursor_pids: list[int] = []
        for p in procs:
            cursor_pids.append(p.pid)
            result.evidence_details.setdefault("process_entries", []).append({
                "pid": p.pid, "cmdline": p.cmdline,
            })

        strength = 0.70
        self._log(f"Found Cursor process(es): {cursor_pids}", verbose)

        agent_exec_found = False
        agent_exec_has_shells = False

        for p in procs[:10]:
            if "agent-exec" in p.cmdline:
                agent_exec_found = True
                result.evidence_details["agent_exec_pid"] = p.pid
                self._log(f"  agent-exec extension host found: PID {p.pid}", verbose)

                child_pids = get_child_pids(p.pid)
                for cpid in child_pids[:8]:
                    child = get_process_info(cpid)
                    if child and _SHELL_NAMES.search(child.name):
                        agent_exec_has_shells = True
                        result.evidence_details.setdefault(
                            "agent_exec_shell_children", []
                        ).append(child.cmdline)

        cursorsan_procs = find_processes("cursorsan")
        if cursorsan_procs:
            result.evidence_details["cursorsan_detected"] = True
            self._log("  cursorsan sandbox process detected", verbose)

        if agent_exec_found and agent_exec_has_shells:
            strength = 0.95
            self._dynamic_tool_class = "C"
            self._log("  Class C escalation: agent-exec with shell children", verbose)
        elif agent_exec_found:
            strength = 0.85
            self._dynamic_tool_class = "C"
            self._log("  Class C: agent-exec found (no active shell children)", verbose)
        else:
            self._log("  Class A: Cursor running without agent-exec", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for Cursor data directory, ai-tracking DB, agent transcripts, and git trailers."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        data_dir = self._paths.data_dir
        if data_dir is None or not data_dir.is_dir():
            self._log("No Cursor data directory found", verbose)
            return strength

        strength = 0.60
        self._log(f"Found {data_dir}", verbose)

        try:
            file_count = sum(1 for f in data_dir.rglob("*") if f.is_file())
            total_size = sum(f.stat().st_size for f in data_dir.rglob("*") if f.is_file())
            most_recent = max(
                (f.stat().st_mtime for f in data_dir.rglob("*") if f.is_file()),
                default=0,
            )
            result.evidence_details["cursor_dir"] = {
                "file_count": file_count,
                "total_size_bytes": total_size,
                "most_recent_mtime": most_recent,
            }
            self._log(f"  {file_count} files, {total_size:,} bytes", verbose)
        except (PermissionError, OSError) as exc:
            self._log(f"  Error reading directory: {exc}", verbose)

        tracking_db = data_dir / "ai-tracking" / "ai-code-tracking.db"
        if tracking_db.is_file():
            strength = max(strength, 0.85)
            try:
                result.evidence_details["ai_tracking_db"] = {
                    "size_bytes": tracking_db.stat().st_size,
                    "mtime": tracking_db.stat().st_mtime,
                }
            except OSError:
                pass
            self._log("  ai-code-tracking.db found (attribution anchor)", verbose)

        transcript_count = 0
        projects_dir = data_dir / "projects"
        if projects_dir.is_dir():
            try:
                for jsonl in projects_dir.rglob("agent-transcripts/*/*.jsonl"):
                    transcript_count += 1
                    if transcript_count >= 50:
                        break
            except (PermissionError, OSError):
                pass

        if transcript_count > 0:
            strength = max(strength, 0.90)
            result.evidence_details["agent_transcript_count"] = transcript_count
            self._log(f"  {transcript_count} agent transcript file(s) found", verbose)

        plans_dir = data_dir / "plans"
        if plans_dir.is_dir():
            try:
                plan_files = list(plans_dir.glob("*.plan.md"))
                if plan_files:
                    result.evidence_details["plan_file_count"] = len(plan_files)
            except (PermissionError, OSError):
                pass

        git_trailers = self._find_madewith_trailers(verbose)
        if git_trailers:
            strength = max(strength, 0.80)
            result.evidence_details["git_madewith_trailers"] = git_trailers
            self._log(f"  Made-with: Cursor trailers in {len(git_trailers)} repo(s)", verbose)

        config_dir = self._paths.config_dir
        if config_dir and config_dir.is_dir():
            result.evidence_details["app_support_dir_exists"] = True

        return strength

    def _find_madewith_trailers(self, verbose: bool) -> list[dict[str, str]]:
        """Scan common project paths for git repos with Made-with: Cursor trailers.

        Caps at MAX_REPOS_TO_SCAN repos to bound execution time.
        """
        results: list[dict[str, str]] = []
        search_dirs = [
            Path.home() / d for d in
            ["Documents", "Projects", "repos", "src", "code"]
        ]
        repos_scanned = 0

        for parent in search_dirs:
            if not parent.is_dir():
                continue
            for candidate in parent.iterdir():
                if repos_scanned >= MAX_REPOS_TO_SCAN:
                    self._log(
                        f"  Git trailer scan: hit {MAX_REPOS_TO_SCAN}-repo cap, stopping",
                        verbose,
                    )
                    return results
                git_dir = candidate / ".git"
                if not git_dir.is_dir():
                    continue
                repos_scanned += 1
                log = self._run_cmd(
                    ["git", "-C", str(candidate), "log", "--all",
                     "--format=%b", "-50"],
                    timeout=5,
                )
                if log and log.returncode == 0:
                    for line in log.stdout.splitlines():
                        if re.search(r"Made-with:\s*Cursor", line, re.IGNORECASE):
                            results.append({
                                "repo": str(candidate),
                                "trailer": line.strip(),
                            })
                            break
        return results

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for TLS connections owned by Cursor PIDs."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        cursor_pids: set[int] = {
            e["pid"] for e in result.evidence_details.get("process_entries", [])
        }
        if not cursor_pids:
            self._log("  No Cursor PIDs to check for network connections", verbose)
            return strength

        conns = get_connections(pids=cursor_pids)
        tls_connections = [
            c for c in conns
            if c.remote_port == 443 and c.status == "ESTABLISHED"
        ]

        if tls_connections:
            strength = 0.75
            result.evidence_details["cursor_tls_connections"] = len(tls_connections)
            self._log(f"  {len(tls_connections)} TLS connection(s) from Cursor PIDs", verbose)

            agent_exec_pid = result.evidence_details.get("agent_exec_pid")
            if agent_exec_pid:
                agent_exec_conns = [c for c in tls_connections if c.pid == agent_exec_pid]
                if agent_exec_conns:
                    result.evidence_details["agent_exec_network"] = len(agent_exec_conns)
                    self._log(
                        f"  {len(agent_exec_conns)} connection(s) from agent-exec",
                        verbose,
                    )
        elif cursor_pids:
            strength = 0.50
            self._log("  Cursor process found but no TLS connections captured", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user, git config, and code signature."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_entries = result.evidence_details.get("process_entries", [])
        if process_entries:
            first_pid = process_entries[0]["pid"]
            info = get_process_info(first_pid)
            if info and info.username:
                result.evidence_details["process_user"] = info.username
                strength = 0.30

        git_email = self._run_cmd(["git", "config", "--global", "user.email"])
        if git_email and git_email.returncode == 0 and git_email.stdout.strip():
            result.evidence_details["git_user_email"] = git_email.stdout.strip()
            strength = max(strength, 0.40)

        install_dir = self._paths.install_dir
        if install_dir:
            sig = verify_code_signature(install_dir)
            if sig and sig.signed:
                subject = sig.subject or ""
                if "Hilary Stout" in subject or "VDXQ22DGB9" in subject or "Cursor" in subject:
                    result.evidence_details["code_signature_valid"] = True
                    strength = max(strength, 0.55)
                    self._log("  Code signature verified (Cursor Inc.)", verbose)

        return min(strength, 0.55)

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for agentic execution patterns and recent activity."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if result.evidence_details.get("agent_exec_shell_children"):
            strength = 0.90
            self._log("  Agent-exec with active shell children", verbose)

        now = time.time()
        recent_threshold = 3600

        data_dir = self._paths.data_dir
        if data_dir:
            projects_dir = data_dir / "projects"
            if projects_dir.is_dir():
                try:
                    for jsonl in projects_dir.rglob("agent-transcripts/*/*.jsonl"):
                        if (now - jsonl.stat().st_mtime) < recent_threshold:
                            strength = max(strength, 0.85)
                            result.evidence_details["recent_agent_transcripts"] = True
                            self._log("  Recent agent transcript (modified within 1h)", verbose)
                            break
                except (PermissionError, OSError):
                    pass

        if result.evidence_details.get("git_madewith_trailers"):
            strength = max(strength, 0.80)

        tracking_db_info = result.evidence_details.get("ai_tracking_db", {})
        db_mtime = tracking_db_info.get("mtime", 0)
        if db_mtime > 0 and (now - db_mtime) < recent_threshold:
            strength = max(strength, 0.70)
            self._log("  ai-code-tracking.db modified recently", verbose)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        if result.signals.identity < 0.55:
            result.penalties.append(("weak_identity_correlation", 0.05))

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("agent_exec_shell_children"):
            summaries.append("agent-exec with active shell children (Class C)")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("agent_exec_pid"):
            summaries.append("agent-exec extension host detected (Class C)")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("process_entries"):
            summaries.append("Cursor IDE running (Class A)")
            result.action_type = "read"
            result.action_risk = "R1"

        cursor_dir_info = result.evidence_details.get("cursor_dir", {})
        if cursor_dir_info:
            count = cursor_dir_info.get("file_count", 0)
            summaries.append(f"~/.cursor/ directory with {count} files")

        if result.evidence_details.get("ai_tracking_db"):
            summaries.append("ai-code-tracking.db present")

        if result.evidence_details.get("agent_transcript_count"):
            count = result.evidence_details["agent_transcript_count"]
            summaries.append(f"{count} agent transcript(s)")

        if result.evidence_details.get("git_madewith_trailers"):
            summaries.append("Made-with: Cursor trailers in git history")

        if result.evidence_details.get("code_signature_valid"):
            summaries.append("code signature verified (Cursor Inc.)")

        if result.evidence_details.get("cursorsan_detected"):
            summaries.append("cursorsan sandbox process active")

        result.action_summary = "; ".join(summaries) if summaries else "No Cursor signals detected"
