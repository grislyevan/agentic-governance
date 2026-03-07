"""GPT-Pilot detection module (Class C — Autonomous Executor, project-generation focus).

GPT-Pilot (github.com/Pythagora-io/gpt-pilot) is an AI agent that generates entire
applications from natural language descriptions. It runs as a Python process with a
long-lived orchestration loop (generate → run → validate → regenerate), produces
high file churn, and creates a distinctive `.gpt-pilot/` state directory.

Detection anchors (priority order from Playbook Section 4.9):
  1. `gpt-pilot` or `pythagora` CLI process (named binary or Python module)
  2. `.gpt-pilot/` state directory in project workspaces
  3. `gpt-pilot` or `pythagora` pip package installation
  4. High file-churn workspace artifacts (sudden project tree creation)
  5. Network connections to LLM APIs aligned with generation phases
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)
HOME = Path.home()
MAX_WORKSPACES_TO_SCAN = 8
GPT_PILOT_STATE_DIR_NAME = ".gpt-pilot"


class GPTPilotScanner(BaseScanner):
    """Detects GPT-Pilot via five-layer signal model with behavior as primary anchor."""

    @property
    def tool_name(self) -> str:
        return "GPT-Pilot"

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
        """Detect GPT-Pilot version via pip show."""
        for pkg in ("gpt-pilot", "pythagora", "gpt_pilot"):
            proc = self._run_cmd(["pip", "show", pkg], timeout=10)
            if proc and proc.returncode == 0 and proc.stdout.strip():
                for line in proc.stdout.splitlines():
                    if line.strip().lower().startswith("version:"):
                        version = line.split(":", 1)[1].strip()
                        if version:
                            self._log(f"Version from pip show ({pkg}): {version}", verbose)
                            return version
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for gpt-pilot / pythagora process and generation loop children."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        for pattern in ("gpt-pilot", "gpt_pilot", "pythagora"):
            proc = self._run_cmd(["pgrep", "-fl", pattern])
            if not (proc and proc.returncode == 0 and proc.stdout.strip()):
                continue
            for line in proc.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid, cmdline = parts
                if "pgrep" in cmdline.lower() or "collector" in cmdline.lower():
                    continue
                if re.search(r'(gpt.pilot|pythagora)', cmdline, re.IGNORECASE):
                    result.evidence_details.setdefault("process_entries", []).append({
                        "pid": pid, "cmdline": cmdline,
                    })
                    strength = 0.75
                    self._log(f"  GPT-Pilot process found: PID {pid}", verbose)

                    detail = self._run_cmd(["ps", "-p", pid, "-o", "pid,ppid,user,command"])
                    if detail and detail.returncode == 0:
                        result.evidence_details["process_detail"] = detail.stdout.strip()
                        for dl in detail.stdout.splitlines()[1:]:
                            fields = dl.split()
                            if len(fields) >= 3:
                                result.evidence_details["process_user"] = fields[2]

                    # Check for generate→run→correct child processes
                    children = self._run_cmd(["pgrep", "-P", pid])
                    if children and children.returncode == 0 and children.stdout.strip():
                        for cpid in children.stdout.strip().splitlines()[:15]:
                            child_info = self._run_cmd(["ps", "-p", cpid, "-o", "pid,command"])
                            if child_info and child_info.returncode == 0:
                                child_cmd = child_info.stdout.strip()
                                if re.search(r'(python|node|bash|sh|npm|pip|pytest)', child_cmd):
                                    result.evidence_details.setdefault(
                                        "generation_children", []
                                    ).append(child_cmd)

        if result.evidence_details.get("generation_children"):
            strength = 0.90
            result.evidence_details["generation_loop_active"] = True
            self._log(
                f"  Generation loop active: {len(result.evidence_details['generation_children'])} child processes",
                verbose,
            )

        if strength == 0.0:
            self._log("No gpt-pilot/pythagora process found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Scan for .gpt-pilot/ state directories and pip installation."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        # Check pip installation
        installed = False
        for pkg in ("gpt-pilot", "pythagora", "gpt_pilot"):
            pip_check = self._run_cmd(["pip", "show", pkg], timeout=10)
            if pip_check and pip_check.returncode == 0 and pip_check.stdout.strip():
                installed = True
                strength = 0.45
                result.evidence_details["pip_installed"] = pkg
                self._log(f"  {pkg} package installed (pip)", verbose)
                break

        # Scan workspaces for .gpt-pilot/ state directories
        state_dirs = self._find_state_dirs(verbose)
        if state_dirs:
            strength = max(strength, 0.75)
            result.evidence_details["state_dirs"] = [str(d) for d in state_dirs]
            self._log(f"  .gpt-pilot/ state in {len(state_dirs)} workspace(s)", verbose)

            # Inspect the most recent state dir
            for state_dir in state_dirs[:2]:
                self._inspect_state_dir(state_dir, result, verbose)

        # Check for workspace directory in home
        for workspace_name in ("workspace", "gpt-pilot-workspace", "pythagora-workspace"):
            workspace = HOME / workspace_name
            if workspace.is_dir():
                try:
                    dir_count = sum(1 for d in workspace.iterdir() if d.is_dir())
                    if dir_count > 0:
                        result.evidence_details.setdefault("workspace_dirs", []).append(
                            {"path": str(workspace), "project_count": dir_count}
                        )
                        strength = max(strength, 0.60)
                        self._log(f"  Workspace dir: {workspace} ({dir_count} projects)", verbose)
                except (PermissionError, OSError) as exc:
                    logger.debug("Could not read workspace dir %s: %s", workspace, exc)

        return strength

    def _find_state_dirs(self, verbose: bool) -> list[Path]:
        """Search repos and workspaces for .gpt-pilot/ directories."""
        results: list[Path] = []
        search_dirs = [HOME / d for d in ("Documents", "Projects", "repos", "src", "code", "workspace")]
        workspaces_scanned = 0

        for parent in search_dirs:
            if not parent.is_dir():
                continue
            try:
                for candidate in parent.iterdir():
                    if workspaces_scanned >= MAX_WORKSPACES_TO_SCAN:
                        return results
                    if not candidate.is_dir():
                        continue
                    state_dir = candidate / GPT_PILOT_STATE_DIR_NAME
                    if state_dir.is_dir():
                        results.append(state_dir)
                        workspaces_scanned += 1
            except (PermissionError, OSError):
                continue

        return results

    def _inspect_state_dir(self, state_dir: Path, result: ScanResult, verbose: bool) -> None:
        """Extract metadata from a .gpt-pilot/ state directory."""
        try:
            files = list(state_dir.rglob("*"))
            file_count = sum(1 for f in files if f.is_file())
            result.evidence_details["state_dir_file_count"] = file_count
            self._log(f"  State dir {state_dir}: {file_count} files", verbose)
        except (PermissionError, OSError) as exc:
            logger.debug("Could not inspect state dir %s: %s", state_dir, exc)

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for LLM API connections from gpt-pilot processes."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        pilot_pids = {e["pid"] for e in result.evidence_details.get("process_entries", [])}
        if not pilot_pids:
            return strength

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if not (lsof and lsof.returncode == 0):
            return strength

        llm_patterns = ["api.openai.com", "api.anthropic.com", ":11434", ":1234"]
        burst_connections: list[str] = []

        for line in lsof.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] not in pilot_pids:
                continue
            if "ESTABLISHED" in line:
                burst_connections.append(line.strip())
                for pattern in llm_patterns:
                    if pattern in line:
                        result.evidence_details.setdefault("llm_connections", []).append(line.strip())
                        break

        if result.evidence_details.get("llm_connections"):
            strength = 0.55
            self._log(
                f"  {len(result.evidence_details['llm_connections'])} LLM API connection(s)",
                verbose,
            )
        elif burst_connections:
            strength = 0.35
            result.evidence_details["unresolved_connections"] = len(burst_connections)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user and API key presence."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.40
            result.evidence_details["identity_user"] = process_user
        elif result.evidence_details.get("pip_installed") or result.evidence_details.get("state_dirs"):
            import getpass
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.30

        for key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if os.environ.get(key_name):
                result.evidence_details.setdefault("api_keys_present", []).append(key_name)
                strength = max(strength, 0.50)
                self._log(f"  API key in env: {key_name}", verbose)

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for mass file generation and generate→validate→regenerate patterns."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if result.evidence_details.get("generation_loop_active"):
            strength = 0.85
            self._log("  Generate→run→correct loop active", verbose)

        # Check for high file churn (sudden project tree creation)
        now = time.time()
        recent_threshold = 3600  # 1 hour
        for workspace_entry in result.evidence_details.get("workspace_dirs", []):
            workspace_path = Path(workspace_entry.get("path", ""))
            if not workspace_path.is_dir():
                continue
            try:
                recent_files = [
                    f for f in workspace_path.rglob("*")
                    if f.is_file() and (now - f.stat().st_mtime) < recent_threshold
                ]
                if len(recent_files) > 20:
                    strength = max(strength, 0.80)
                    result.evidence_details["high_file_churn"] = len(recent_files)
                    result.evidence_details["generation_workspace"] = str(workspace_path)
                    self._log(
                        f"  High file churn: {len(recent_files)} files in last hour", verbose
                    )
            except (PermissionError, OSError) as exc:
                logger.debug("Could not check recent files in workspace %s: %s", workspace_path, exc)

        if result.evidence_details.get("state_dirs"):
            strength = max(strength, 0.60)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        self._penalize_stale_artifacts(result, amount=0.05)

        if result.signals.process > 0 and not result.evidence_details.get("llm_connections"):
            result.penalties.append(("unresolved_process_network_linkage", 0.05))

        self._penalize_weak_identity(result, threshold=0.4, amount=0.10)

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("generation_loop_active"):
            summaries.append("GPT-Pilot generation loop active (generate→run→correct)")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("high_file_churn"):
            summaries.append("GPT-Pilot: high file churn (mass generation)")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("process_entries"):
            summaries.append("GPT-Pilot process running")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("state_dirs"):
            summaries.append("GPT-Pilot state directories found (not running)")
            result.action_type = "read"
            result.action_risk = "R1"

        if result.evidence_details.get("state_dirs"):
            count = len(result.evidence_details["state_dirs"])
            summaries.append(f".gpt-pilot/ state in {count} workspace(s)")

        if result.evidence_details.get("high_file_churn"):
            summaries.append(
                f"WARNING: {result.evidence_details['high_file_churn']} files created in last hour"
            )
            result.action_risk = "R3"

        if result.evidence_details.get("api_keys_present"):
            keys = result.evidence_details["api_keys_present"]
            summaries.append(f"API keys in env: {', '.join(keys)}")

        result.action_summary = "; ".join(summaries) if summaries else "No GPT-Pilot signals detected"
