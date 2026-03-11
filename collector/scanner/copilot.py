"""GitHub Copilot detection module (Class A -- Assistive IDE Extension).

Copilot runs as a VS Code extension inside the shared extension host process.
Process-layer detection alone cannot attribute activity to Copilot -- cross-layer
correlation with file artifacts (extension directory) and identity (GitHub auth
state) is required.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from compat import (
    find_processes,
    get_connections,
    get_credential_store_entry,
    get_tool_paths,
    ToolPaths,
)

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)


class CopilotScanner(BaseScanner):
    """Detects GitHub Copilot extension via five-layer signal model."""

    def __init__(self, *, event_store=None, **kwargs) -> None:
        super().__init__(event_store=event_store, **kwargs)
        self._paths: ToolPaths = get_tool_paths("vscode")

    @property
    def tool_name(self) -> str:
        return "GitHub Copilot"

    @property
    def tool_class(self) -> str:
        return "A"

    def scan(self, verbose: bool = False) -> ScanResult:
        self._paths = get_tool_paths("vscode")
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
        """Detect Copilot extension version from extension manifest (package.json)."""
        ext_dir = self._find_copilot_extension_dir()
        if not ext_dir:
            return None
        package_json = ext_dir / "package.json"
        if not package_json.is_file():
            return None
        try:
            data = json.loads(package_json.read_text())
            if isinstance(data, dict) and "version" in data:
                version = str(data["version"]).strip()
                if version:
                    self._log(f"Version from extension manifest: {version}", verbose)
                    return version
        except (json.JSONDecodeError, PermissionError, OSError) as exc:
            logger.debug("Could not read Copilot extension manifest %s: %s", package_json, exc)
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for VS Code process tree including extension host."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        procs = find_processes("Code")
        procs = [
            p for p in procs
            if "collector" not in p.cmdline.lower()
            and re.search(r"(Visual Studio Code|Code Helper|Electron.*Code)", p.cmdline)
        ]

        if not procs:
            self._log("No VS Code process found", verbose)
            return strength

        plugin_host_found = False

        for p in procs:
            result.evidence_details.setdefault("process_entries", []).append({
                "pid": p.pid, "cmdline": p.cmdline,
            })
            if "Plugin" in p.cmdline or "extension-host" in p.cmdline.lower():
                plugin_host_found = True

        strength = 0.50
        self._log(f"Found VS Code process(es): {len(procs)} total", verbose)
        if plugin_host_found:
            result.evidence_details["extension_host_found"] = True
            self._log("  Code Helper (Plugin) extension host found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for Copilot extension directory and VS Code logs."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        copilot_ext_dir = self._find_copilot_extension_dir()
        if copilot_ext_dir:
            strength = 0.85
            result.evidence_details["copilot_extension_dir"] = str(copilot_ext_dir)
            try:
                file_count = sum(1 for f in copilot_ext_dir.rglob("*") if f.is_file())
                result.evidence_details["copilot_extension_files"] = file_count
            except (PermissionError, OSError) as exc:
                logger.debug("Could not count files in Copilot extension dir %s: %s", copilot_ext_dir, exc)
            self._log(f"  Copilot extension found: {copilot_ext_dir.name}", verbose)
        else:
            self._log("  No Copilot extension directory found", verbose)

        config_dir = self._paths.config_dir
        if config_dir:
            cached_vsix_dir = config_dir / "CachedExtensionVSIXs"
            if cached_vsix_dir.is_dir():
                try:
                    for entry in cached_vsix_dir.iterdir():
                        if entry.name.startswith("github.copilot-chat"):
                            result.evidence_details["cached_vsix"] = str(entry)
                            strength = max(strength, 0.70)
                            self._log(f"  Cached Copilot VSIX: {entry.name}", verbose)
                            break
                except (PermissionError, OSError) as exc:
                    logger.debug("Could not iterate CachedExtensionVSIXs dir %s: %s", cached_vsix_dir, exc)

        auth_log = self._find_github_auth_log()
        if auth_log:
            result.evidence_details["github_auth_log_path"] = str(auth_log)
            try:
                content = auth_log.read_text(errors="replace")
                if "Got 0 sessions" in content:
                    result.evidence_details["github_auth_state"] = "unauthenticated"
                    self._log("  GitHub auth: 0 sessions (not authenticated)", verbose)
                else:
                    session_match = re.search(r'Got\s+(\d+)\s+sessions?', content)
                    if session_match and int(session_match.group(1)) > 0:
                        result.evidence_details["github_auth_state"] = "authenticated"
                        result.evidence_details["github_session_count"] = int(
                            session_match.group(1)
                        )
                        self._log(
                            f"  GitHub auth: {session_match.group(1)} session(s)", verbose
                        )
            except (PermissionError, OSError) as exc:
                self._log(f"  Error reading auth log: {exc}", verbose)

        return strength

    def _find_copilot_extension_dir(self) -> Path | None:
        """Find the github.copilot-chat extension in the VS Code extensions directory."""
        ext_dir = self._paths.extensions_dir
        if ext_dir is None or not ext_dir.is_dir():
            return None
        try:
            for entry in ext_dir.iterdir():
                if entry.is_dir() and entry.name.startswith("github.copilot-chat"):
                    return entry
        except (PermissionError, OSError) as exc:
            logger.debug("Could not iterate extensions dir %s: %s", ext_dir, exc)
        return None

    def _find_github_auth_log(self) -> Path | None:
        """Find the most recent GitHub Authentication log in VS Code logs."""
        log_dir = self._paths.log_dir
        if log_dir is None or not log_dir.is_dir():
            return None
        try:
            session_dirs = sorted(
                (d for d in log_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            for session_dir in session_dirs[:3]:
                auth_log = session_dir / "vscode.github-authentication" / "GitHub Authentication.log"
                if auth_log.is_file():
                    return auth_log
        except (PermissionError, OSError) as exc:
            logger.debug("Could not find GitHub auth log in log dir %s: %s", log_dir, exc)
        return None

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for VS Code network connections."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        vscode_pids: set[int] = {
            e["pid"] for e in result.evidence_details.get("process_entries", [])
        }
        if not vscode_pids:
            return strength

        conns = get_connections(pids=vscode_pids)
        https_conns = [
            c for c in conns
            if c.remote_port == 443 and c.status == "ESTABLISHED"
        ]

        if https_conns:
            strength = 0.55
            result.evidence_details["vscode_https_connections"] = len(https_conns)
            self._log(f"  {len(https_conns)} HTTPS connection(s) from VS Code PIDs", verbose)
        else:
            strength = 0.30
            self._log("  VS Code running but no HTTPS connections captured", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check credential store for GitHub auth and VS Code telemetry for entitlements."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        has_cred = get_credential_store_entry("vscodevscode.github-authentication")
        if has_cred:
            strength = 0.80
            result.evidence_details["github_keychain_found"] = True
            self._log("  GitHub auth token found in credential store", verbose)
        else:
            result.evidence_details["github_keychain_found"] = False
            strength = 0.30
            self._log("  No GitHub auth in credential store (not authenticated)", verbose)

        entitlement_info = self._check_chat_entitlement(verbose)
        if entitlement_info:
            result.evidence_details.update(entitlement_info)
            entitled = entitlement_info.get("chat_entitlement")
            registered = entitlement_info.get("chat_registered")
            if entitled and registered:
                strength = max(strength, 0.85)
                self._log("  chatEntitlement=1 + chatRegistered=1 (active)", verbose)
            elif entitled and not registered:
                strength = max(strength, 0.40)
                self._log("  chatEntitlement=1 + chatRegistered=0 (dormant)", verbose)

        return strength

    def _check_chat_entitlement(self, verbose: bool) -> dict[str, bool] | None:
        """Search recent VS Code telemetry logs for chatEntitlement/chatRegistered."""
        log_dir = self._paths.log_dir
        if log_dir is None or not log_dir.is_dir():
            return None
        try:
            session_dirs = sorted(
                (d for d in log_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            for session_dir in session_dirs[:3]:
                try:
                    for log_file in session_dir.rglob("*.log"):
                        content = log_file.read_text(errors="replace")
                        entitled_match = re.search(r'chatEntitlement["\s:]+(\d)', content)
                        registered_match = re.search(r'chatRegistered["\s:]+(\d)', content)
                        if entitled_match or registered_match:
                            return {
                                "chat_entitlement": bool(
                                    entitled_match and entitled_match.group(1) == "1"
                                ),
                                "chat_registered": bool(
                                    registered_match and registered_match.group(1) == "1"
                                ),
                            }
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError) as exc:
            logger.debug("Could not iterate log dir for chat entitlement %s: %s", log_dir, exc)
        return None

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for Copilot-specific behavioral signals in VS Code logs."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.25

        copilot_flags_found = self._check_copilot_experiment_flags(verbose)
        if copilot_flags_found:
            strength = max(strength, 0.40)
            result.evidence_details["copilot_experiment_flags"] = True
            self._log("  Copilot A/B experiment flags detected", verbose)

        auth_state = result.evidence_details.get("github_auth_state")
        if auth_state == "authenticated":
            strength = max(strength, 0.60)
            self._log("  Authenticated -- active behavioral signals expected", verbose)

        return strength

    def _check_copilot_experiment_flags(self, verbose: bool) -> bool:
        """Check VS Code telemetry logs for Copilot-specific A/B experiment flags."""
        log_dir = self._paths.log_dir
        if log_dir is None or not log_dir.is_dir():
            return False
        try:
            session_dirs = sorted(
                (d for d in log_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            for session_dir in session_dirs[:2]:
                try:
                    for log_file in session_dir.rglob("*.log"):
                        content = log_file.read_text(errors="replace")
                        if re.search(r'dwcopilot|copilot_t_ci', content):
                            return True
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError) as exc:
            logger.debug("Could not iterate log dir for Copilot experiment flags %s: %s", log_dir, exc)
        return False

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        if result.evidence_details.get("extension_host_found"):
            result.penalties.append(("extension_host_shared_by_all_extensions", 0.05))

        auth_state = result.evidence_details.get("github_auth_state")
        if auth_state != "authenticated" and not result.evidence_details.get("github_keychain_found"):
            result.penalties.append(("weak_identity_unauthenticated", 0.05))

        vscode_pids = result.evidence_details.get("process_entries", [])
        https_count = result.evidence_details.get("vscode_https_connections", 0)
        if vscode_pids and https_count > 0:
            result.penalties.append(("unresolved_copilot_vs_vscode_traffic", 0.05))

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        copilot_installed = bool(result.evidence_details.get("copilot_extension_dir"))
        authenticated = (
            result.evidence_details.get("github_auth_state") == "authenticated"
            or result.evidence_details.get("github_keychain_found") is True
        )

        if copilot_installed and authenticated:
            summaries.append("Copilot extension installed + GitHub authenticated")
            result.action_type = "read"
            result.action_risk = "R2"
        elif copilot_installed:
            summaries.append("Copilot extension installed (not authenticated)")
            result.action_type = "read"
            result.action_risk = "R1"
        elif result.evidence_details.get("process_entries"):
            summaries.append("VS Code running (Copilot not confirmed)")
            result.action_type = "read"
            result.action_risk = "R1"

        if result.evidence_details.get("copilot_extension_files"):
            count = result.evidence_details["copilot_extension_files"]
            summaries.append(f"extension: {count} files")

        entitlement = result.evidence_details.get("chat_entitlement")
        registered = result.evidence_details.get("chat_registered")
        if entitlement is not None:
            state = "active" if (entitlement and registered) else "dormant" if entitlement else "none"
            summaries.append(f"chatEntitlement state: {state}")

        if result.evidence_details.get("copilot_experiment_flags"):
            summaries.append("Copilot A/B flags detected in telemetry")

        result.action_summary = (
            "; ".join(summaries) if summaries else "No GitHub Copilot signals detected"
        )
