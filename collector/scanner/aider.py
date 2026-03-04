"""Aider detection module (Class C — Autonomous Executor, repo mutation focus).

Aider is a CLI tool that uses LLMs to make targeted code changes directly in git
repositories. Unlike Claude Code, aider has a distinctive named binary (`aider`),
leaves deterministic file artifacts (`.aider*`), and operates entirely through git.

Detection anchors (priority order from Playbook Section 4.8):
  1. `aider` process in process listing (named binary)
  2. `.aider.conf.yml` or `.aider.chat.history.md` in repositories
  3. Git commits attributed to aider (commit message patterns)
  4. `aider-chat` pip package installation
  5. Network connections to configured LLM API
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .base import BaseScanner, LayerSignals, ScanResult

HOME = Path.home()
MAX_REPOS_TO_SCAN = 10
AIDER_ARTIFACTS = frozenset({
    ".aider.conf.yml",
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.tags.cache.v3",
    ".aiderignore",
})
AIDER_COMMIT_PATTERNS = re.compile(
    r'(aider:|feat.*aider|chore.*aider|refactor.*aider)', re.IGNORECASE
)


class AiderScanner(BaseScanner):
    """Detects Aider CLI via five-layer signal model with process as primary anchor."""

    @property
    def tool_name(self) -> str:
        return "Aider"

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

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Detect Aider version via CLI or pip show."""
        proc = self._run_cmd(["aider", "--version"], timeout=5)
        if proc and proc.returncode == 0 and proc.stdout.strip():
            match = re.search(r"(\d+\.\d+[\.\d]*)", proc.stdout.strip())
            if match:
                version = match.group(1)
                self._log(f"Version from CLI: {version}", verbose)
                return version

        proc = self._run_cmd(["pip", "show", "aider-chat"], timeout=10)
        if proc and proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if line.strip().lower().startswith("version:"):
                    version = line.split(":", 1)[1].strip()
                    if version:
                        self._log(f"Version from pip show: {version}", verbose)
                        return version
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for running aider process and child git/shell subprocesses."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        proc = self._run_cmd(["pgrep", "-fl", "aider"])
        if not (proc and proc.returncode == 0 and proc.stdout.strip()):
            self._log("No aider process found", verbose)
            return strength

        aider_pids: list[str] = []
        for line in proc.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            pid, cmdline = parts
            if "pgrep" in cmdline.lower() or "collector" in cmdline.lower():
                continue
            if re.search(r'\baider\b', cmdline, re.IGNORECASE):
                aider_pids.append(pid)
                result.evidence_details.setdefault("process_entries", []).append({
                    "pid": pid, "cmdline": cmdline,
                })
                self._log(f"  Aider process found: PID {pid}", verbose)

        if not aider_pids:
            return strength

        strength = 0.75
        detail = self._run_cmd(["ps", "-p", aider_pids[0], "-o", "pid,ppid,user,command"])
        if detail and detail.returncode == 0:
            result.evidence_details["process_detail"] = detail.stdout.strip()
            for dl in detail.stdout.splitlines()[1:]:
                fields = dl.split()
                if len(fields) >= 3:
                    result.evidence_details["process_user"] = fields[2]

        # Check for child git/shell/test processes (prompt-edit-commit loop)
        for pid in aider_pids[:3]:
            children = self._run_cmd(["pgrep", "-P", pid])
            if not (children and children.returncode == 0 and children.stdout.strip()):
                continue
            for cpid in children.stdout.strip().splitlines()[:10]:
                child_info = self._run_cmd(["ps", "-p", cpid, "-o", "pid,command"])
                if child_info and child_info.returncode == 0:
                    child_cmd = child_info.stdout.strip()
                    if re.search(r'(git|pytest|python|bash|sh|npm)', child_cmd):
                        result.evidence_details.setdefault("agentic_children", []).append(child_cmd)

        if result.evidence_details.get("agentic_children"):
            strength = 0.90
            result.evidence_details["prompt_edit_loop_active"] = True
            self._log(
                f"  Child processes: {result.evidence_details['agentic_children'][:3]}", verbose
            )

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Scan repos for .aider* artifacts and check for pip installation."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        # Check pip installation
        pip_check = self._run_cmd(["pip", "show", "aider-chat"], timeout=10)
        if pip_check and pip_check.returncode == 0 and pip_check.stdout.strip():
            strength = 0.50
            result.evidence_details["pip_installed"] = True
            self._log("  aider-chat package installed (pip)", verbose)

            for line in pip_check.stdout.splitlines():
                if line.strip().lower().startswith("location:"):
                    install_path = line.split(":", 1)[1].strip()
                    result.evidence_details["install_path"] = install_path
                    break

        # Scan repos for .aider* artifacts
        aider_artifacts = self._find_aider_artifacts(verbose)
        if aider_artifacts:
            strength = max(strength, 0.75)
            result.evidence_details["aider_artifacts"] = aider_artifacts
            self._log(f"  Found .aider* artifacts in {len(aider_artifacts)} repo(s)", verbose)

        # Check for ~/.aider/ config/cache dir
        aider_cache = HOME / ".aider"
        if aider_cache.is_dir():
            try:
                file_count = sum(1 for f in aider_cache.rglob("*") if f.is_file())
                result.evidence_details["aider_cache_dir"] = {"file_count": file_count}
                strength = max(strength, 0.60)
                self._log(f"  ~/.aider/ found ({file_count} files)", verbose)
            except (PermissionError, OSError):
                pass

        return strength

    def _find_aider_artifacts(self, verbose: bool) -> list[dict[str, str | list[str]]]:
        """Scan repos for .aider* artifacts, capped at MAX_REPOS_TO_SCAN."""
        results: list[dict[str, str | list[str]]] = []
        search_dirs = [HOME / d for d in ("Documents", "Projects", "repos", "src", "code")]
        repos_scanned = 0

        for parent in search_dirs:
            if not parent.is_dir():
                continue
            try:
                for candidate in parent.iterdir():
                    if repos_scanned >= MAX_REPOS_TO_SCAN:
                        self._log(
                            f"  Artifact scan: hit {MAX_REPOS_TO_SCAN}-repo cap, stopping",
                            verbose,
                        )
                        return results
                    if not (candidate / ".git").is_dir():
                        continue
                    repos_scanned += 1
                    found_artifacts: list[str] = []
                    for artifact_name in AIDER_ARTIFACTS:
                        artifact_path = candidate / artifact_name
                        if artifact_path.exists():
                            found_artifacts.append(artifact_name)

                    if found_artifacts:
                        results.append({
                            "repo": str(candidate),
                            "artifacts": found_artifacts,
                        })
                        self._log(
                            f"  .aider* artifacts in {candidate.name}: {found_artifacts}",
                            verbose,
                        )
            except (PermissionError, OSError):
                continue

        return results

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for LLM API connections from aider processes."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        aider_pids = {e["pid"] for e in result.evidence_details.get("process_entries", [])}
        if not aider_pids:
            return strength

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if not (lsof and lsof.returncode == 0):
            return strength

        llm_patterns = ["api.openai.com", "api.anthropic.com", ":11434", ":1234"]
        connections: list[str] = []

        for line in lsof.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] not in aider_pids:
                continue
            if "ESTABLISHED" in line:
                connections.append(line.strip())
                for pattern in llm_patterns:
                    if pattern in line:
                        result.evidence_details.setdefault("llm_connections", []).append(line.strip())
                        self._log(f"  LLM API connection: {line.strip()[:80]}", verbose)
                        break

        if result.evidence_details.get("llm_connections"):
            strength = 0.55
        elif connections:
            strength = 0.35
            result.evidence_details["unresolved_connections"] = len(connections)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user, git config, and API key in environment."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.40
            result.evidence_details["identity_user"] = process_user
        elif result.evidence_details.get("pip_installed") or result.evidence_details.get("aider_artifacts"):
            import getpass
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.30

        git_email = self._run_cmd(["git", "config", "--global", "user.email"])
        if git_email and git_email.returncode == 0 and git_email.stdout.strip():
            result.evidence_details["git_user_email"] = git_email.stdout.strip()
            strength = max(strength, 0.45)

        for key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if os.environ.get(key_name):
                result.evidence_details.setdefault("api_keys_present", []).append(key_name)
                strength = max(strength, 0.55)
                self._log(f"  API key in env: {key_name}", verbose)

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for agentic prompt-edit-commit loops and recent activity."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if result.evidence_details.get("prompt_edit_loop_active"):
            strength = 0.85
            self._log("  Prompt-edit-commit loop active (aider + git children)", verbose)

        aider_artifacts = result.evidence_details.get("aider_artifacts", [])
        if aider_artifacts:
            # Check recency of artifacts
            now = time.time()
            recent_repos = 0
            for entry in aider_artifacts:
                repo_path = Path(str(entry.get("repo", "")))
                for artifact_name in entry.get("artifacts", []):
                    artifact = repo_path / str(artifact_name)
                    try:
                        if artifact.exists() and (now - artifact.stat().st_mtime) < 86400:
                            recent_repos += 1
                            break
                    except OSError:
                        pass

            if recent_repos > 0:
                strength = max(strength, 0.75)
                result.evidence_details["recent_artifact_repos"] = recent_repos
                self._log(f"  .aider* artifacts modified in last 24h in {recent_repos} repo(s)", verbose)
            else:
                strength = max(strength, 0.55)

        # Check git commits attributable to aider (direct API key context)
        aider_commits = self._find_aider_commits(verbose)
        if aider_commits:
            strength = max(strength, 0.80)
            result.evidence_details["aider_git_commits"] = aider_commits
            self._log(f"  Aider-attributed commits found in {len(aider_commits)} repo(s)", verbose)

        return strength

    def _find_aider_commits(self, verbose: bool) -> list[dict[str, str]]:
        """Scan repos for git commits attributable to aider."""
        results: list[dict[str, str]] = []
        search_dirs = [HOME / d for d in ("Documents", "Projects", "repos", "src", "code")]
        repos_scanned = 0

        for parent in search_dirs:
            if not parent.is_dir():
                continue
            try:
                for candidate in parent.iterdir():
                    if repos_scanned >= MAX_REPOS_TO_SCAN:
                        return results
                    if not (candidate / ".git").is_dir():
                        continue
                    repos_scanned += 1
                    log = self._run_cmd(
                        ["git", "-C", str(candidate), "log", "--all", "--format=%s", "-30"],
                        timeout=5,
                    )
                    if log and log.returncode == 0:
                        for line in log.stdout.splitlines():
                            if AIDER_COMMIT_PATTERNS.search(line):
                                results.append({
                                    "repo": str(candidate),
                                    "commit_subject": line.strip(),
                                })
                                break
            except (PermissionError, OSError):
                continue

        return results

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        if result.signals.file > 0 and result.signals.process == 0:
            result.penalties.append(("non_default_artifact_paths", 0.05))

        if result.signals.process > 0 and not result.evidence_details.get("llm_connections"):
            result.penalties.append(("unresolved_process_network_linkage", 0.05))

        if result.signals.identity < 0.4:
            result.penalties.append(("weak_identity_correlation", 0.10))

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("prompt_edit_loop_active"):
            summaries.append("Aider active with prompt-edit-commit loop")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("process_entries"):
            summaries.append("Aider process running")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("aider_artifacts"):
            summaries.append("Aider installed, not running")
            result.action_type = "read"
            result.action_risk = "R1"

        if result.evidence_details.get("aider_artifacts"):
            repos = len(result.evidence_details["aider_artifacts"])
            summaries.append(f".aider* artifacts in {repos} repo(s)")

        if result.evidence_details.get("aider_git_commits"):
            repos = len(result.evidence_details["aider_git_commits"])
            summaries.append(f"aider commits found in {repos} repo(s)")

        if result.evidence_details.get("api_keys_present"):
            keys = result.evidence_details["api_keys_present"]
            summaries.append(f"API keys in env: {', '.join(keys)}")

        result.action_summary = "; ".join(summaries) if summaries else "No Aider signals detected"
