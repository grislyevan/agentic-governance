"""Claude Code detection module (Class C — Autonomous Executor)."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

from compat import find_processes, get_child_pids, get_connections, get_process_info

from .base import BaseScanner, LayerSignals, ScanResult
from .constants import MAX_REPOS_TO_SCAN

logger = logging.getLogger(__name__)


class ClaudeCodeScanner(BaseScanner):
    """Detects Claude Code CLI presence and activity via five-layer signal model."""

    @property
    def tool_name(self) -> str:
        return "Claude Code"

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

        if any(s > 0.0 for s in [process_strength, file_strength, network_strength,
                                   identity_strength, behavior_strength]):
            result.detected = True

        self._apply_penalties(result)
        self._determine_action(result)
        result.tool_version = self._detect_version(verbose)
        if result.detected:
            result.process_patterns = ["claude"]

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Detect Claude Code CLI version via --version or config under install paths."""
        proc = self._run_cmd(["claude", "--version"], timeout=5)
        if proc and proc.returncode == 0 and proc.stdout.strip():
            version = proc.stdout.strip()
            if version:
                self._log(f"Version from CLI: {version}", verbose)
                return version
        claude_dir = Path.home() / ".claude"
        for candidate in (claude_dir / "settings.json", claude_dir / "settings.local.json"):
            if not candidate.is_file():
                continue
            try:
                data = json.loads(candidate.read_text())
                if isinstance(data, dict) and "version" in data:
                    ver = str(data["version"]).strip()
                    if ver:
                        self._log(f"Version from config: {ver}", verbose)
                        return ver
            except (json.JSONDecodeError, PermissionError, OSError):
                continue
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for running claude/claude-code processes and child chains."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0
        own_pid = os.getpid()
        own_ppid = os.getppid()

        procs = find_processes("claude")
        procs = [
            p for p in procs
            if p.pid not in (own_pid, own_ppid)
            and "pgrep" not in p.cmdline.lower()
            and re.search(r'\bclaude\b', p.cmdline, re.IGNORECASE)
            and "collector" not in p.cmdline.lower()
            and "main.py" not in p.cmdline
        ]

        if procs:
            claude_pids: list[int] = [p.pid for p in procs]
            for p in procs:
                result.evidence_details.setdefault("process_entries", []).append({
                    "pid": p.pid, "cmdline": p.cmdline
                })

            strength = 0.7
            self._log(f"Found claude process(es): {claude_pids}", verbose)

            for pid in claude_pids[:3]:
                detail = get_process_info(pid)
                if detail:
                    result.evidence_details["process_detail"] = (
                        f"{detail.pid} {detail.ppid or ''} {detail.username or ''} {detail.cmdline}"
                    )

                child_pids = get_child_pids(pid)
                if child_pids:
                    result.evidence_details["child_pids"] = child_pids
                    strength = 0.85
                    self._log(f"Child processes found: {child_pids}", verbose)

                    for cpid in child_pids[:5]:
                        child = get_process_info(cpid)
                        if child and re.search(r'(zsh|bash|python|git|node)', child.cmdline):
                            strength = 0.90
                            result.evidence_details.setdefault("agentic_children", []).append(
                                child.cmdline
                            )
        else:
            self._log("No claude process found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for ~/.claude/ directory, settings, and evasion indicators."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0
        claude_dir = Path.home() / ".claude"

        if claude_dir.is_dir():
            strength = 0.6
            self._log(f"Found {claude_dir}", verbose)

            try:
                file_count = sum(1 for _ in claude_dir.rglob("*") if _.is_file())
                total_size = sum(f.stat().st_size for f in claude_dir.rglob("*") if f.is_file())
                most_recent = max(
                    (f.stat().st_mtime for f in claude_dir.rglob("*") if f.is_file()),
                    default=0
                )
                result.evidence_details["claude_dir"] = {
                    "file_count": file_count,
                    "total_size_bytes": total_size,
                    "most_recent_mtime": most_recent,
                }
                if file_count > 50:
                    strength = 0.85
                if file_count > 200:
                    strength = 0.95
                self._log(f"  {file_count} files, {total_size} bytes", verbose)
            except (PermissionError, OSError) as exc:
                self._log(f"  Error reading directory: {exc}", verbose)

            for settings_name in ("settings.json", "settings.local.json"):
                settings_path = claude_dir / settings_name
                if settings_path.is_file():
                    result.evidence_details.setdefault("settings_files", []).append(str(settings_path))
                    self._check_evasion_settings(settings_path, result, verbose)

            for project_settings in claude_dir.glob("projects/**/settings.json"):
                self._check_evasion_settings(project_settings, result, verbose)

        home_dirs = [Path.home() / "Documents", Path.home() / "Projects",
                     Path.home() / "repos", Path.home() / "src", Path.home() / "code"]
        for parent in home_dirs:
            if parent.is_dir():
                for d in parent.iterdir():
                    if d.is_dir():
                        local_claude = d / ".claude"
                        if local_claude.is_dir():
                            result.evidence_details.setdefault("project_claude_dirs", []).append(str(local_claude))
                            if strength < 0.7:
                                strength = 0.7

        return strength

    def _check_evasion_settings(self, path: Path, result: ScanResult, verbose: bool) -> None:
        """Scan settings file for Co-Authored-By suppression (evasion indicator)."""
        try:
            content = path.read_text()
            data = json.loads(content)
        except (json.JSONDecodeError, PermissionError, OSError):
            return

        evasion_found = False

        if isinstance(data, dict):
            if data.get("includeCoAuthoredBy") is False:
                evasion_found = True
                result.evidence_details.setdefault("evasion_indicators", []).append(
                    f"{path}: includeCoAuthoredBy=false"
                )

            attribution = data.get("attribution", {})
            if isinstance(attribution, dict) and attribution.get("commit") == "":
                evasion_found = True
                result.evidence_details.setdefault("evasion_indicators", []).append(
                    f"{path}: attribution.commit=empty"
                )

        if evasion_found:
            result.evasion_boost += 0.15
            self._log(f"  EVASION: Co-Authored-By suppression in {path.name}", verbose)

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for connections to api.anthropic.com and npm registry."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if lsof and lsof.returncode == 0:
            for line in lsof.stdout.splitlines():
                if "api.anthropic.com" in line or "anthropic" in line.lower():
                    strength = max(strength, 0.5)
                    result.evidence_details.setdefault("network_connections", []).append(line.strip())
                    self._log("  Found anthropic connection", verbose)

                if "registry.npmjs.org" in line and "claude" in line.lower():
                    strength = max(strength, 0.35)
                    result.evidence_details.setdefault("npm_connections", []).append(line.strip())

        netstat = self._run_cmd(["netstat", "-an"])
        if netstat and netstat.returncode == 0:
            for line in netstat.stdout.splitlines():
                if "443" in line and "ESTABLISHED" in line:
                    result.evidence_details.setdefault("active_tls_count", 0)
                    result.evidence_details["active_tls_count"] += 1

        if strength == 0.0:
            self._log("  No anthropic network connections found (expected without EDR)", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check for API keys in env and git Co-Authored-By trailers."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        if os.environ.get("ANTHROPIC_API_KEY"):
            strength = 0.6
            result.evidence_details["anthropic_api_key_set"] = True
            self._log("  ANTHROPIC_API_KEY found in environment", verbose)

        oauth_backup_dir = Path.home() / ".claude" / "backups"
        if oauth_backup_dir.is_dir():
            for f in oauth_backup_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text())
                    if isinstance(data, dict) and any(
                        k in data for k in ("email", "accountUuid", "orgUuid")
                    ):
                        strength = max(strength, 0.80)
                        result.evidence_details["oauth_profile"] = {
                            "email": data.get("email"),
                            "org_role": data.get("orgRole"),
                        }
                        self._log("  OAuth profile found in backups", verbose)
                        break
                except (json.JSONDecodeError, PermissionError, OSError):
                    continue

        git_trailers = self._find_coauthored_trailers(verbose)
        if git_trailers:
            strength = max(strength, 0.85)
            result.evidence_details["git_coauthored_trailers"] = git_trailers
            self._log(f"  Co-Authored-By trailers found in {len(git_trailers)} repo(s)", verbose)

        git_identity = self._run_cmd(["git", "config", "--global", "user.email"])
        if git_identity and git_identity.returncode == 0 and git_identity.stdout.strip():
            result.evidence_details["git_user_email"] = git_identity.stdout.strip()

        return strength

    def _find_coauthored_trailers(self, verbose: bool) -> list[dict[str, str]]:
        """Scan common project paths for git repos with anthropic Co-Authored-By trailers.

        Caps at MAX_REPOS_TO_SCAN repos to bound execution time on machines
        with many repositories (each repo gets a 5s timeout).
        """
        results: list[dict[str, str]] = []
        search_dirs = [
            Path.home() / d for d in
            ["Documents", "Projects", "repos", "src", "code", "claude-lab"]
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
                    timeout=5
                )
                if log and log.returncode == 0:
                    for line in log.stdout.splitlines():
                        if re.search(r"Co-Authored-By:.*anthropic\.com", line, re.IGNORECASE):
                            results.append({
                                "repo": str(candidate),
                                "trailer": line.strip(),
                            })
                            break
        return results

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for agentic execution patterns."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if result.evidence_details.get("agentic_children"):
            strength = 0.75
            self._log("  Agentic child process patterns detected", verbose)

        claude_dir = Path.home() / ".claude"
        if claude_dir.is_dir():
            now = time.time()
            recent_threshold = 3600  # 1 hour
            try:
                recent_files = [
                    f for f in claude_dir.rglob("*")
                    if f.is_file() and (now - f.stat().st_mtime) < recent_threshold
                ]
                if recent_files:
                    strength = max(strength, 0.7)
                    result.evidence_details["recent_claude_files"] = len(recent_files)
                    self._log(f"  {len(recent_files)} files modified in last hour", verbose)
                    if len(recent_files) > 20:
                        strength = max(strength, 0.9)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not list recent files in ~/.claude/ for behavior scan: %s", exc)

        if result.evidence_details.get("git_coauthored_trailers"):
            strength = max(strength, 0.8)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalty conditions from Appendix B."""
        self._penalize_missing_process_chain(result, "child_pids", amount=0.15)

        if result.signals.network > 0 and result.signals.process > 0:
            has_attribution = any(
                "claude" in str(c).lower()
                for c in result.evidence_details.get("network_connections", [])
            )
            if not has_attribution:
                result.penalties.append(("unresolved_process_network_linkage", 0.10))
        elif result.signals.network == 0 and result.signals.process > 0:
            result.penalties.append(("unresolved_process_network_linkage", 0.10))

        if result.signals.file > 0 and result.signals.process == 0:
            claude_dir_info = result.evidence_details.get("claude_dir", {})
            mtime = claude_dir_info.get("most_recent_mtime", 0)
            if mtime > 0 and (time.time() - mtime) > 86400:
                result.penalties.append(("stale_artifact_only", 0.10))

        self._penalize_weak_identity(result, threshold=0.3, amount=0.10)

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.signals.process > 0:
            summaries.append("Claude Code CLI process detected")
            result.action_type = "exec"
            result.action_risk = "R2"

        if result.signals.file > 0:
            dir_info = result.evidence_details.get("claude_dir", {})
            count = dir_info.get("file_count", 0)
            summaries.append(f"~/.claude/ directory with {count} files")

        if result.evidence_details.get("agentic_children"):
            summaries.append("agentic child processes (shell/git/python)")
            result.action_risk = "R3"

        if result.evidence_details.get("git_coauthored_trailers"):
            summaries.append("Co-Authored-By trailers in git history")

        if result.evidence_details.get("evasion_indicators"):
            summaries.append("EVASION: Co-Authored-By suppression detected")
            result.action_risk = "R3"

        if result.evidence_details.get("oauth_profile"):
            summaries.append("OAuth identity profile found")

        if summaries:
            result.action_summary = "; ".join(summaries)
        elif result.signals.identity > 0:
            result.action_summary = (
                "Environment or artifact hint only; no running Claude Code process or strong artifact."
            )
        else:
            result.action_summary = "No Claude Code signals detected"
