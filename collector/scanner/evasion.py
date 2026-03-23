"""Evasion detection scanner (Rule C6 from Playbook v0.4).

Detects attempts to suppress AI tool attribution or evade detection:
  E1: Git hook trailer stripping (commit-msg hooks that remove Co-Authored-By)
  E2: Global template hooks (init.templatedir with stripping hooks)
  E3: Force-push after amend/rebase (reflog analysis)
  E4: Renamed or wrapped AI tool binaries
  E5: Cursor Made-with trailer suppression (settings.json)
  E6: Agent disable/kill loop (process/diagnostics evidence of repeated agent interruption)
  E7: Config tamper / policy suppression (weakening collector or policy-related config)
  E8: Telemetry shaping (provider downgrade/suppression inferred from capability drift)

Evasion signals feed into the confidence engine as evasion_boost values,
which increase (not decrease) the confidence score. The reasoning: if
someone is actively trying to hide tool usage, that is itself a strong
governance signal.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scanner.base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)

HOOK_STRIP_PATTERNS = [
    re.compile(r"co-authored-by", re.IGNORECASE),
    re.compile(r"grep\s+-v.*co.?authored", re.IGNORECASE),
    re.compile(r"sed.*co.?authored", re.IGNORECASE),
    re.compile(r"awk.*co.?authored", re.IGNORECASE),
    re.compile(r"trailer.*remove", re.IGNORECASE),
]

KNOWN_AI_BINARIES = {
    "claude", "cursor", "ollama", "aider", "interpreter",
    "gpt-pilot", "cline", "continue", "lm-studio", "lmstudio",
    "copilot", "openclaw",
}

# E4: Subprocess names that are normal children of AI tools (do not treat as renamed binary).
NORMAL_SUBPROCESS_NAMES = {
    "node",
    "electron",
    "shipit",
    "zsh",
    "bash",
    "sh",
}

# E4: Parent process names that indicate an AI tool; only flag renamed binaries when parent is in this set.
AI_TOOL_PROCESS_NAMES = {
    "cursor",
    "electron",
    "code",
    "claude",
    "aider",
    "ollama",
    "interpreter",
    "gpt-pilot",
    "cline",
    "continue",
    "lm-studio",
    "lmstudio",
    "copilot",
    "openclaw",
}

CURSOR_SETTINGS_PATHS = [
    Path.home() / ".cursor" / "settings.json",
    Path.home() / ".config" / "Cursor" / "User" / "settings.json",
    Path.home() / "Library" / "Application Support" / "Cursor" / "User" / "settings.json",
    Path.home() / "AppData" / "Roaming" / "Cursor" / "User" / "settings.json",
]

GIT_SEARCH_ROOTS = [
    Path.home(),
    Path.home() / "Documents",
    Path.home() / "code",
    Path.home() / "projects",
    Path.home() / "src",
    Path.home() / "dev",
    Path.home() / "repos",
    Path.home() / "workspace",
]

MAX_REPOS_TO_SCAN = 50
MAX_REFLOG_ENTRIES = 200

# E6: Process name/cmdline patterns that suggest kill/pkill targeting the agent.
AGENT_KILL_CMD_PATTERN = re.compile(
    r"\b(kill|pkill|killall|taskkill)\b.*\b(detec|collector|agentic|agent\.py|detec-agent)\b",
    re.IGNORECASE,
)
E6_LOOKBACK_SECONDS = 300
E6_MIN_KILL_EVENTS = 2

# E7: Collector config paths to check for weakening (attribution suppression).
# config_loader._platform_config_paths() defines the actual search order; we check same locations.
def _collector_config_paths() -> list[Path]:
    paths: list[Path] = []
    if sys.platform == "darwin":
        paths.append(Path("/Library/Application Support/Detec/collector.json"))
        paths.append(Path.home() / "Library" / "Application Support" / "Detec" / "collector.json")
    elif sys.platform == "win32":
        paths.append(Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Detec" / "collector.json")
    else:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        paths.append(config_home / "detec" / "collector.json")
    paths.append(Path(__file__).resolve().parent.parent / "config" / "collector.json")
    return paths


@dataclass
class EvasionFinding:
    vector: str
    description: str
    path: str | None = None
    boost: float = 0.0


class EvasionScanner(BaseScanner):
    """Cross-cutting scanner that detects evasion patterns across the system."""

    @property
    def tool_name(self) -> str:
        return "Evasion Detection"

    @property
    def tool_class(self) -> str:
        return "X"

    def scan(
        self,
        verbose: bool = False,
        diagnostics_context: dict[str, Any] | None = None,
    ) -> ScanResult:
        result = ScanResult(
            detected=False,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
        )
        findings: list[EvasionFinding] = []
        diagnostics_context = diagnostics_context or {}

        self._log("Scanning for evasion indicators...", verbose)

        findings.extend(self._check_global_hooks(verbose))
        findings.extend(self._check_template_hooks(verbose))
        findings.extend(self._check_repo_hooks(verbose))
        findings.extend(self._check_force_push_patterns(verbose))
        findings.extend(self._check_renamed_binaries(verbose))
        findings.extend(self._check_cursor_settings(verbose))
        findings.extend(self._check_agent_interruption_patterns(verbose, diagnostics_context))
        findings.extend(self._check_config_tamper(verbose))
        findings.extend(
            self._check_telemetry_shaping(verbose, diagnostics_context),
        )

        if findings:
            result.detected = True
            result.evidence_details["evasion_findings"] = [
                {"vector": f.vector, "description": f.description, "path": f.path}
                for f in findings
            ]
            result.evasion_boost = sum(f.boost for f in findings)
            result.evasion_boost = min(result.evasion_boost, 0.50)
            result.signals.behavior = 0.8
            result.signals.file = 0.6
            result.action_summary = (
                f"Evasion: {len(findings)} indicator(s) found"
            )
            self._log(
                f"Found {len(findings)} evasion indicator(s), "
                f"total boost: +{result.evasion_boost:.2f}",
                verbose,
            )
        else:
            self._log("No evasion indicators found.", verbose)

        return result

    def _check_global_hooks(self, verbose: bool) -> list[EvasionFinding]:
        """E1: Check git global core.hooksPath for trailer-stripping hooks."""
        findings = []
        hooks_path = self._get_git_config("core.hooksPath")
        if not hooks_path:
            return findings

        hooks_dir = Path(hooks_path).expanduser()
        if not hooks_dir.is_dir():
            return findings

        commit_msg_hook = hooks_dir / "commit-msg"
        if commit_msg_hook.is_file():
            content = self._safe_read(commit_msg_hook)
            if content and self._has_strip_pattern(content):
                findings.append(EvasionFinding(
                    vector="E1-global-hook",
                    description="Global commit-msg hook strips Co-Authored-By trailers",
                    path=str(commit_msg_hook),
                    boost=0.15,
                ))
                self._log(f"  E1: Global hook strips trailers: {commit_msg_hook}", verbose)

        return findings

    def _check_template_hooks(self, verbose: bool) -> list[EvasionFinding]:
        """E2: Check init.templatedir for template hooks with stripping patterns."""
        findings = []
        template_dir = self._get_git_config("init.templatedir")
        if not template_dir:
            return findings

        tmpl_path = Path(template_dir).expanduser()
        hooks_dir = tmpl_path / "hooks"
        if not hooks_dir.is_dir():
            return findings

        commit_msg_hook = hooks_dir / "commit-msg"
        if commit_msg_hook.is_file():
            content = self._safe_read(commit_msg_hook)
            if content and self._has_strip_pattern(content):
                findings.append(EvasionFinding(
                    vector="E2-template-hook",
                    description="Template commit-msg hook strips Co-Authored-By trailers",
                    path=str(commit_msg_hook),
                    boost=0.20,
                ))
                self._log(f"  E2: Template hook strips trailers: {commit_msg_hook}", verbose)

        return findings

    def _check_repo_hooks(self, verbose: bool) -> list[EvasionFinding]:
        """E1: Scan local repo hooks for trailer-stripping commit-msg hooks."""
        findings = []
        repos = self._find_git_repos()

        for repo in repos[:MAX_REPOS_TO_SCAN]:
            hook = repo / "hooks" / "commit-msg"
            if not hook.is_file():
                continue
            content = self._safe_read(hook)
            if content and self._has_strip_pattern(content):
                findings.append(EvasionFinding(
                    vector="E1-repo-hook",
                    description="Repo commit-msg hook strips Co-Authored-By trailers",
                    path=str(hook),
                    boost=0.15,
                ))
                self._log(f"  E1: Repo hook strips trailers: {hook}", verbose)

        return findings

    def _check_force_push_patterns(self, verbose: bool) -> list[EvasionFinding]:
        """E3: Check git reflog for amend followed by force-push patterns."""
        findings = []
        repos = self._find_git_repos()

        for repo in repos[:MAX_REPOS_TO_SCAN]:
            reflog_path = repo / "logs" / "HEAD"
            if not reflog_path.is_file():
                continue

            content = self._safe_read(reflog_path)
            if not content:
                continue

            lines = content.strip().splitlines()[-MAX_REFLOG_ENTRIES:]
            amend_seen = False
            for line in lines:
                if "amend" in line.lower() or "rebase" in line.lower():
                    amend_seen = True
                elif amend_seen and "push" in line.lower() and ("--force" in line or "force-with-lease" in line):
                    findings.append(EvasionFinding(
                        vector="E3-force-push",
                        description="Force-push after amend/rebase detected in reflog",
                        path=str(reflog_path.parent.parent),
                        boost=0.10,
                    ))
                    self._log(f"  E3: Force-push after amend in {repo}", verbose)
                    amend_seen = False
                    break

        return findings

    def _check_renamed_binaries(self, verbose: bool) -> list[EvasionFinding]:
        """E4: Look for AI tool processes running under non-standard names.

        Only flags when the process is a direct child of an AI tool (parent in
        AI_TOOL_PROCESS_NAMES) and the executable name is not a known normal
        subprocess (e.g. node, electron).
        """
        findings = []
        # Build pid -> (ppid, comm) for parent check. macOS: -eo; Linux: -eo.
        ps_table = self._run_cmd(["ps", "-eo", "pid=,ppid=,comm="])
        pid_to_ppid_comm: dict[int, tuple[int, str]] = {}
        if ps_table and ps_table.returncode == 0:
            for line in ps_table.stdout.splitlines():
                parts = line.strip().split(None, 2)
                if len(parts) >= 3:
                    try:
                        pid = int(parts[0])
                        ppid = int(parts[1])
                        comm = (parts[2] if len(parts) > 2 else "").strip().lower()
                        pid_to_ppid_comm[pid] = (ppid, comm)
                    except ValueError:
                        continue

        ps_result = self._run_cmd(["ps", "aux"])
        if not ps_result or ps_result.returncode != 0:
            return findings

        for line in ps_result.stdout.splitlines()[1:]:
            parts = line.split(None, 10)
            if len(parts) < 11:
                continue
            try:
                pid = int(parts[1])
            except ValueError:
                continue
            cmd = parts[10].lower()
            exe_name = Path(parts[10].split()[0]).stem.lower()
            if exe_name in NORMAL_SUBPROCESS_NAMES:
                continue
            # Require parent to be an AI tool process (only flag children of AI tools).
            if pid in pid_to_ppid_comm:
                ppid, _ = pid_to_ppid_comm[pid]
                parent_comm = pid_to_ppid_comm.get(ppid, (0, ""))[1].strip().lower()
                if parent_comm not in AI_TOOL_PROCESS_NAMES:
                    continue
            else:
                continue

            for binary in KNOWN_AI_BINARIES:
                if binary in cmd and binary not in exe_name and exe_name not in KNOWN_AI_BINARIES:
                    findings.append(EvasionFinding(
                        vector="E4-renamed-binary",
                        description=f"AI tool '{binary}' running under different name '{exe_name}'",
                        path=parts[10].split()[0],
                        boost=0.08,
                    ))
                    self._log(f"  E4: Renamed binary: {exe_name} (contains {binary})", verbose)
                    break

        return findings

    def _check_cursor_settings(self, verbose: bool) -> list[EvasionFinding]:
        """E5: Check Cursor settings for Made-with trailer suppression."""
        findings = []

        for settings_path in CURSOR_SETTINGS_PATHS:
            if not settings_path.is_file():
                continue
            content = self._safe_read(settings_path)
            if not content:
                continue
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue

            if not isinstance(data, dict):
                continue

            git_enabled = data.get("git.enabled", True)
            if git_enabled is False:
                findings.append(EvasionFinding(
                    vector="E5-cursor-git-disabled",
                    description="Cursor git integration disabled (suppresses Made-with trailer)",
                    path=str(settings_path),
                    boost=0.10,
                ))
                self._log(f"  E5: Cursor git disabled: {settings_path}", verbose)

            telemetry = data.get("telemetry.telemetryLevel", "all")
            if telemetry == "off":
                findings.append(EvasionFinding(
                    vector="E5-cursor-telemetry-off",
                    description="Cursor telemetry disabled",
                    path=str(settings_path),
                    boost=0.05,
                ))

        return findings

    def _check_agent_interruption_patterns(
        self,
        verbose: bool,
        diagnostics_context: dict[str, Any] | None = None,
    ) -> list[EvasionFinding]:
        """E6: Detect process/diagnostics evidence of repeated agent kill or disable.

        Uses event_store process events to find kill/pkill/taskkill cmdlines
        targeting the collector or agent; repeated occurrences suggest a kill loop.
        Also uses diagnostics_context.scan_failures: multiple scan failures in one
        cycle suggest repeated agent interruption (E3-02).
        """
        findings: list[EvasionFinding] = []
        ctx = diagnostics_context or {}

        if self._event_store:
            try:
                since = datetime.now(timezone.utc) - timedelta(seconds=E6_LOOKBACK_SECONDS)
                events = self._event_store.get_process_events(since=since)
                kill_events = [e for e in events if AGENT_KILL_CMD_PATTERN.search(e.cmdline)]
                if len(kill_events) >= E6_MIN_KILL_EVENTS:
                    findings.append(EvasionFinding(
                        vector="E6-agent-kill-loop",
                        description="Repeated agent kill/pkill patterns in process events",
                        path=None,
                        boost=0.12,
                    ))
                    self._log(
                        f"  E6: Agent kill loop: {len(kill_events)} kill-like event(s) in last {E6_LOOKBACK_SECONDS}s",
                        verbose,
                    )
            except Exception:
                logger.debug("E6 check failed (event_store)", exc_info=True)

        scan_failures = ctx.get("scan_failures") or []
        if len(scan_failures) >= 2 and not any(f.vector == "E6-agent-kill-loop" for f in findings):
            findings.append(EvasionFinding(
                vector="E6-agent-kill-loop",
                description="Repeated scan failures in this cycle (possible agent interruption)",
                path=None,
                boost=0.10,
            ))
            self._log(
                f"  E6: Repeated scan failures: {len(scan_failures)} (possible interruption)",
                verbose,
            )

        return findings

    def _check_config_tamper(self, verbose: bool) -> list[EvasionFinding]:
        """E7: Detect suspicious collector config that weakens attribution or reporting."""
        findings: list[EvasionFinding] = []
        for config_path in _collector_config_paths():
            if not config_path.is_file():
                continue
            content = self._safe_read(config_path)
            if not content:
                continue
            try:
                data = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            # Weakening: api_url empty/missing (suppresses reporting), or dry_run true.
            api_url = data.get("api_url") or ""
            if isinstance(api_url, str) and api_url.strip() == "" and "api_key" in data:
                findings.append(EvasionFinding(
                    vector="E7-config-tamper",
                    description="Collector config has api_url empty with api_key set (reporting suppressed)",
                    path=str(config_path),
                    boost=0.15,
                ))
                self._log(f"  E7: Config tamper (api_url empty): {config_path}", verbose)
            if data.get("dry_run") is True and data.get("api_url"):
                findings.append(EvasionFinding(
                    vector="E7-config-tamper",
                    description="Collector config forces dry_run with api_url set",
                    path=str(config_path),
                    boost=0.10,
                ))
                self._log(f"  E7: Config tamper (dry_run with api): {config_path}", verbose)
        return findings

    def _check_telemetry_shaping(
        self,
        verbose: bool,
        diagnostics_context: dict[str, Any],
    ) -> list[EvasionFinding]:
        """E8: Infer intentional telemetry downgrade from capability drift and provider context.

        When capability_drift is non-empty and provider is polling, we treat it as
        possible telemetry shaping (downgrade/suppression).
        """
        findings: list[EvasionFinding] = []
        drift = diagnostics_context.get("capability_drift") or []
        provider = (diagnostics_context.get("provider_name") or "").lower()
        if not drift or provider != "polling":
            return findings
        findings.append(EvasionFinding(
            vector="E8-telemetry-shaping",
            description="Telemetry capability drift while using polling (possible downgrade/suppression)",
            path=None,
            boost=0.10,
        ))
        self._log(
            f"  E8: Telemetry shaping: capability_drift={drift}, provider={provider}",
            verbose,
        )
        return findings

    def _find_git_repos(self) -> list[Path]:
        """Discover .git directories in common code locations."""
        repos: list[Path] = []
        seen: set[str] = set()

        for root in GIT_SEARCH_ROOTS:
            if not root.is_dir():
                continue
            try:
                for entry in root.iterdir():
                    if not entry.is_dir():
                        continue
                    git_dir = entry / ".git"
                    if git_dir.is_dir() and str(git_dir) not in seen:
                        seen.add(str(git_dir))
                        repos.append(git_dir)
                    if len(repos) >= MAX_REPOS_TO_SCAN:
                        break
            except PermissionError:
                continue

        return repos

    def _get_git_config(self, key: str) -> str | None:
        """Read a git global config value."""
        result = self._run_cmd(["git", "config", "--global", key])
        if result and result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None

    @staticmethod
    def _safe_read(path: Path, max_size: int = 64 * 1024) -> str | None:
        """Read a file, returning None on error or if too large."""
        try:
            if path.stat().st_size > max_size:
                return None
            return path.read_text(errors="replace")
        except (OSError, PermissionError):
            return None

    @staticmethod
    def _has_strip_pattern(content: str) -> bool:
        """Check if content contains patterns that strip Co-Authored-By trailers."""
        return any(pat.search(content) for pat in HOOK_STRIP_PATTERNS)
