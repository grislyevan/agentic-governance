"""OpenClaw detection module (Class D — Persistent Autonomous Agent).

OpenClaw is a Node.js-based personal AI assistant that runs as a persistent gateway
daemon via LaunchAgent/systemd. It satisfies all four Class D criteria: (1) daemon
persistence with KeepAlive+RunAtLoad, (2) proactive/scheduled execution via
cron/heartbeat, (3) external communication channels (WhatsApp/Telegram/Slack),
and (4) self-modification via a live-reloaded skills system.

Detection anchors (priority order from LAB-RUN-007):
  1. ~/.openclaw/ directory (215 MB, config/credentials/skills/sessions/logs)
  2. openclaw-gateway daemon process with LaunchAgent persistence
  3. Gateway WebSocket listener on localhost:18789
  4. Cleartext credentials in openclaw.json and LaunchAgent plist
  5. Self-authored skills in workspace/skills/
"""

from __future__ import annotations

import getpass
import os
import plistlib
import re
import time
from pathlib import Path

from .base import BaseScanner, LayerSignals, ScanResult

OPENCLAW_DIR = Path.home() / ".openclaw"
LAUNCH_AGENT_PLIST = (
    Path.home() / "Library" / "LaunchAgents" / "ai.openclaw.gateway.plist"
)
GATEWAY_PORT = 18789

CREDENTIAL_ENV_NAMES = frozenset({
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "OPENCLAW_GATEWAY_TOKEN",
    "JIRA_API_TOKEN", "JIRA_EMAIL",
})


class OpenClawScanner(BaseScanner):
    """Detects OpenClaw gateway, config directory, and agentic capabilities via five-layer model."""

    @property
    def tool_name(self) -> str:
        return "OpenClaw"

    @property
    def tool_class(self) -> str:
        return "D"

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

    # ------------------------------------------------------------------
    # Version
    # ------------------------------------------------------------------

    def _detect_version(self, verbose: bool) -> str | None:
        proc = self._run_cmd(["openclaw", "--version"], timeout=5)
        if not proc:
            return None
        combined = (proc.stdout or "").strip() + "\n" + (proc.stderr or "").strip()
        match = re.search(r"(\d+\.\d+\.\d+)", combined)
        if match:
            version = match.group(1)
            self._log(f"Version from CLI: {version}", verbose)
            return version
        return None

    # ------------------------------------------------------------------
    # Layer 1 — Process
    # ------------------------------------------------------------------

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        proc = self._run_cmd(["pgrep", "-fl", "openclaw"])
        if proc and proc.returncode == 0 and proc.stdout.strip():
            for line in proc.stdout.strip().splitlines():
                parts = line.split(None, 1)
                if len(parts) < 2:
                    continue
                pid, cmdline = parts
                if "pgrep" in cmdline.lower() or "collector" in cmdline.lower():
                    continue
                if not re.search(r'openclaw', cmdline, re.IGNORECASE):
                    continue

                result.evidence_details.setdefault("process_entries", []).append({
                    "pid": pid, "cmdline": cmdline,
                })

                if "gateway" in cmdline:
                    strength = 0.90
                    result.evidence_details["daemon_running"] = True
                    self._log(f"  Gateway daemon found: PID {pid}", verbose)
                else:
                    strength = max(strength, 0.60)
                    self._log(f"  CLI process found: PID {pid} ({cmdline})", verbose)

                detail = self._run_cmd(["ps", "-p", pid, "-o", "pid,ppid,user,command"])
                if detail and detail.returncode == 0:
                    result.evidence_details["process_detail"] = detail.stdout.strip()
                    for dl in detail.stdout.splitlines()[1:]:
                        fields = dl.split()
                        if len(fields) >= 3:
                            result.evidence_details["process_user"] = fields[2]

        if self._check_launch_agent(result, verbose):
            strength = max(strength, 0.50)

        if strength == 0.0:
            self._log("No openclaw process found", verbose)

        return strength

    def _check_launch_agent(self, result: ScanResult, verbose: bool) -> bool:
        if not LAUNCH_AGENT_PLIST.is_file():
            return False

        result.evidence_details["launch_agent_plist"] = str(LAUNCH_AGENT_PLIST)
        self._log(f"  LaunchAgent plist found: {LAUNCH_AGENT_PLIST}", verbose)

        try:
            with open(LAUNCH_AGENT_PLIST, "rb") as f:
                plist = plistlib.load(f)

            keep_alive = plist.get("KeepAlive", False)
            run_at_load = plist.get("RunAtLoad", False)
            result.evidence_details["launch_agent_keep_alive"] = keep_alive
            result.evidence_details["launch_agent_run_at_load"] = run_at_load

            if keep_alive and run_at_load:
                self._log("  KeepAlive + RunAtLoad: strongest persistence", verbose)

            env_vars = plist.get("EnvironmentVariables", {})
            embedded_creds = [k for k in env_vars if k in CREDENTIAL_ENV_NAMES]
            if embedded_creds:
                result.evidence_details["plist_embedded_credentials"] = embedded_creds
                self._log(
                    f"  Plist embeds credentials: {', '.join(embedded_creds)}", verbose,
                )

        except (OSError, plistlib.InvalidFileException, Exception):
            pass

        return True

    # ------------------------------------------------------------------
    # Layer 2 — File
    # ------------------------------------------------------------------

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        if not OPENCLAW_DIR.is_dir():
            self._log("No ~/.openclaw/ directory found", verbose)
            return strength

        strength = 0.60
        self._log(f"Found {OPENCLAW_DIR}", verbose)

        try:
            file_count = sum(1 for f in OPENCLAW_DIR.rglob("*") if f.is_file())
            total_size = sum(f.stat().st_size for f in OPENCLAW_DIR.rglob("*") if f.is_file())
            result.evidence_details["openclaw_dir"] = {
                "file_count": file_count,
                "total_size_bytes": total_size,
            }
            self._log(f"  {file_count} files, {total_size:,} bytes", verbose)

            if file_count > 10:
                strength = 0.80
        except (PermissionError, OSError) as exc:
            self._log(f"  Error reading directory: {exc}", verbose)

        config_file = OPENCLAW_DIR / "openclaw.json"
        if config_file.is_file():
            strength = max(strength, 0.85)
            result.evidence_details["config_file"] = True
            self._log("  openclaw.json found (central config)", verbose)

        creds_dir = OPENCLAW_DIR / "credentials"
        if creds_dir.is_dir():
            result.evidence_details["credentials_dir"] = True
            self._log("  credentials/ directory found", verbose)

        skills_dir = OPENCLAW_DIR / "workspace" / "skills"
        if skills_dir.is_dir():
            try:
                skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
                if skill_dirs:
                    result.evidence_details["skill_count"] = len(skill_dirs)
                    result.evidence_details["skill_names"] = [d.name for d in skill_dirs[:20]]
                    strength = max(strength, 0.90)
                    self._log(f"  {len(skill_dirs)} skill(s) in workspace", verbose)
            except (PermissionError, OSError):
                pass

        for subdir_name in ("agents", "memory", "logs", "browser", "devices"):
            subdir = OPENCLAW_DIR / subdir_name
            if subdir.is_dir():
                result.evidence_details.setdefault("subdirectories", []).append(subdir_name)

        exec_approvals = OPENCLAW_DIR / "exec-approvals.json"
        if exec_approvals.is_file():
            result.evidence_details["exec_approvals"] = True
            self._log("  exec-approvals.json found (authorized commands registry)", verbose)

        sessions_path = OPENCLAW_DIR / "agents" / "main" / "sessions" / "sessions.json"
        if sessions_path.is_file():
            result.evidence_details["sessions_file"] = True
            strength = max(strength, 0.85)
            self._log("  Session persistence file found", verbose)

        if LAUNCH_AGENT_PLIST.is_file():
            strength = max(strength, 0.85)

        return strength

    # ------------------------------------------------------------------
    # Layer 3 — Network
    # ------------------------------------------------------------------

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        lsof = self._run_cmd(["lsof", "-i", f":{GATEWAY_PORT}", "-n", "-P"])
        if lsof and lsof.returncode == 0 and lsof.stdout.strip():
            for line in lsof.stdout.splitlines():
                if "LISTEN" in line:
                    strength = 0.75
                    result.evidence_details["gateway_listener"] = line.strip()
                    pid_match = re.search(r'^\S+\s+(\d+)', line)
                    if pid_match:
                        result.evidence_details["gateway_listener_pid"] = pid_match.group(1)
                    self._log(f"  Gateway listener on :{GATEWAY_PORT}", verbose)
                    break

        if strength == 0.0:
            openclaw_pids = {
                e["pid"] for e in result.evidence_details.get("process_entries", [])
            }
            if openclaw_pids:
                lsof_all = self._run_cmd(["lsof", "-i", "-n", "-P"])
                if lsof_all and lsof_all.returncode == 0:
                    for line in lsof_all.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 2 and parts[1] in openclaw_pids:
                            if ":443" in line and "ESTABLISHED" in line:
                                result.evidence_details.setdefault(
                                    "model_api_connections", []
                                ).append(line.strip())
                    if result.evidence_details.get("model_api_connections"):
                        strength = 0.55
                        self._log(
                            f"  {len(result.evidence_details['model_api_connections'])} "
                            f"TLS connection(s) from OpenClaw PIDs",
                            verbose,
                        )

        if strength == 0.0:
            self._log(f"  No gateway listener on :{GATEWAY_PORT}", verbose)

        return strength

    # ------------------------------------------------------------------
    # Layer 4 — Identity
    # ------------------------------------------------------------------

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.30
            result.evidence_details["identity_user"] = process_user
            self._log(f"  Process owner: {process_user}", verbose)
        elif OPENCLAW_DIR.is_dir():
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.30

        api_keys_found: list[str] = []
        for key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY"):
            if os.environ.get(key_name):
                api_keys_found.append(key_name)
        if api_keys_found:
            strength = max(strength, 0.60)
            result.evidence_details["api_keys_present"] = api_keys_found
            self._log(f"  API key(s) in environment: {', '.join(api_keys_found)}", verbose)

        plist_creds = result.evidence_details.get("plist_embedded_credentials", [])
        if plist_creds:
            strength = max(strength, 0.75)
            self._log(
                f"  Credentials embedded in LaunchAgent plist: {', '.join(plist_creds)}",
                verbose,
            )

        if result.evidence_details.get("credentials_dir"):
            strength = max(strength, 0.65)
            self._log("  Credentials directory present (chat platform auth stores)", verbose)

        if result.evidence_details.get("config_file"):
            strength = max(strength, 0.55)

        return strength

    # ------------------------------------------------------------------
    # Layer 5 — Behavior
    # ------------------------------------------------------------------

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        if result.evidence_details.get("skill_count", 0) > 0:
            strength = 0.80
            result.evidence_details["self_modification_evidence"] = True
            self._log(
                f"  Self-authored skills detected ({result.evidence_details['skill_count']})",
                verbose,
            )

        daemon_running = result.evidence_details.get("daemon_running", False)
        keep_alive = result.evidence_details.get("launch_agent_keep_alive", False)
        if daemon_running and keep_alive:
            strength = max(strength, 0.75)
            result.evidence_details["persistent_autonomous_daemon"] = True
            self._log("  Persistent autonomous daemon (KeepAlive + running)", verbose)
        elif daemon_running:
            strength = max(strength, 0.60)

        now = time.time()
        recent_threshold = 3600
        logs_dir = OPENCLAW_DIR / "logs"
        if logs_dir.is_dir():
            try:
                for log_file in logs_dir.iterdir():
                    if log_file.is_file() and (now - log_file.stat().st_mtime) < recent_threshold:
                        result.evidence_details["recent_log_activity"] = True
                        strength = max(strength, 0.65)
                        self._log("  Recent gateway log activity (modified within 1h)", verbose)
                        break
            except (PermissionError, OSError):
                pass

        cron_jobs = OPENCLAW_DIR / "cron" / "jobs.json"
        if cron_jobs.is_file():
            result.evidence_details["cron_infrastructure"] = True
            try:
                content = cron_jobs.read_text(encoding="utf-8").strip()
                if content and content not in ("[]", "{}"):
                    strength = max(strength, 0.85)
                    result.evidence_details["active_cron_jobs"] = True
                    self._log("  Active cron jobs configured (proactive execution)", verbose)
            except (OSError, UnicodeDecodeError):
                pass

        if result.evidence_details.get("exec_approvals"):
            strength = max(strength, 0.55)

        if (
            strength == 0.0
            and OPENCLAW_DIR.is_dir()
            and result.evidence_details.get("config_file")
        ):
            strength = 0.40
            self._log("  Installed with config but daemon not running", verbose)

        return strength

    # ------------------------------------------------------------------
    # Penalties
    # ------------------------------------------------------------------

    def _apply_penalties(self, result: ScanResult) -> None:
        if result.signals.network > 0 and result.signals.process > 0:
            listener_pid = result.evidence_details.get("gateway_listener_pid")
            process_pids = {
                e.get("pid") for e in result.evidence_details.get("process_entries", [])
            }
            if listener_pid and listener_pid not in process_pids:
                result.penalties.append(("unresolved_process_network_linkage", 0.05))

        if result.signals.file > 0 and result.signals.process == 0 and result.signals.network == 0:
            result.penalties.append(("stale_artifact_only", 0.10))

        if result.signals.identity < 0.4:
            result.penalties.append(("weak_identity_correlation", 0.05))

    # ------------------------------------------------------------------
    # Action determination
    # ------------------------------------------------------------------

    def _determine_action(self, result: ScanResult) -> None:
        summaries: list[str] = []

        if result.evidence_details.get("self_modification_evidence"):
            summaries.append("Self-authored skills detected (self-modification)")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("daemon_running"):
            summaries.append("OpenClaw gateway daemon running")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif OPENCLAW_DIR.is_dir():
            summaries.append("OpenClaw installed (daemon not running)")
            result.action_type = "read"
            result.action_risk = "R1"

        if result.evidence_details.get("persistent_autonomous_daemon"):
            summaries.append("KeepAlive + RunAtLoad (auto-restart persistence)")
            result.action_risk = "R3"

        dir_info = result.evidence_details.get("openclaw_dir", {})
        if dir_info:
            size_mb = dir_info.get("total_size_bytes", 0) / (1024 * 1024)
            count = dir_info.get("file_count", 0)
            summaries.append(f"~/.openclaw/ with {count} files ({size_mb:.0f} MB)")

        if result.evidence_details.get("config_file"):
            summaries.append("openclaw.json config present")

        if result.evidence_details.get("skill_count"):
            count = result.evidence_details["skill_count"]
            names = result.evidence_details.get("skill_names", [])
            names_str = f": {', '.join(names[:5])}" if names else ""
            summaries.append(f"{count} self-authored skill(s){names_str}")

        if result.evidence_details.get("gateway_listener"):
            summaries.append(f"gateway listener on localhost:{GATEWAY_PORT}")

        if result.evidence_details.get("plist_embedded_credentials"):
            creds = result.evidence_details["plist_embedded_credentials"]
            summaries.append(f"WARNING: LaunchAgent plist embeds credentials ({', '.join(creds)})")

        if result.evidence_details.get("active_cron_jobs"):
            summaries.append("active cron jobs (proactive execution)")

        if result.evidence_details.get("api_keys_present"):
            keys = result.evidence_details["api_keys_present"]
            summaries.append(f"API keys in env: {', '.join(keys)}")

        result.action_summary = "; ".join(summaries) if summaries else "No OpenClaw signals detected"
