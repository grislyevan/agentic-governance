"""LM Studio detection module (Class B — Local Model Runtime).

LM Studio is an Electron-based GUI app for running local GGUF/safetensors models.
It installs as a standard macOS application and optionally exposes a local OpenAI-
compatible API server on port 1234. Detection anchors (priority order):
  1. ~/Library/Application Support/LM Studio/ — app data directory
  2. /Applications/LM Studio.app — application install
  3. localhost:1234 listener — local server mode enabled
  4. LM Studio process — Electron app running
  5. Downloaded model files (GGUF/safetensors) in configured model path
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from compat import (
    find_processes,
    get_app_version,
    get_listeners,
    get_process_info,
    get_tool_paths,
)

from .base import BaseScanner, LayerSignals, ScanResult
from .constants import LM_STUDIO_API_PORT

logger = logging.getLogger(__name__)
LOCAL_API_PORT = LM_STUDIO_API_PORT

MODEL_EXTENSIONS = frozenset({".gguf", ".safetensors", ".bin", ".ggml"})


class LMStudioScanner(BaseScanner):
    """Detects LM Studio via five-layer signal model."""

    def __init__(self, *, event_store=None, **kwargs) -> None:
        super().__init__(event_store=event_store, **kwargs)
        self._paths = get_tool_paths("lm_studio")

    @property
    def tool_name(self) -> str:
        return "LM Studio"

    @property
    def tool_class(self) -> str:
        return "B"

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
            result.process_patterns = ["lm-studio", "lmstudio", "LM Studio"]

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Detect LM Studio version from Info.plist or app support directory."""
        install_dir = self._paths.install_dir
        if install_dir:
            version = get_app_version(install_dir)
            if version:
                self._log(f"Version from Info.plist: {version}", verbose)
                return str(version)

        # Fallback: version file in app support dir
        config_dir = self._paths.config_dir
        if config_dir is None:
            return None
        version_file = config_dir / "version.json"
        if version_file.is_file():
            try:
                data = json.loads(version_file.read_text())
                if isinstance(data, dict) and "version" in data:
                    return str(data["version"])
            except (json.JSONDecodeError, OSError) as exc:
                logger.debug("Could not read LM Studio version file %s: %s", version_file, exc)

        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for LM Studio Electron process."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        procs = find_processes(r"(?i)(lm.?studio|lmstudio)")
        procs = [p for p in procs if "collector" not in p.cmdline.lower()]

        for p in procs:
            if not re.search(r'(?i)(lm.?studio|lmstudio)', p.cmdline):
                continue
            result.evidence_details.setdefault("process_entries", []).append({
                "pid": p.pid, "cmdline": p.cmdline,
            })
            if "LM Studio" in p.cmdline and ".app" in p.cmdline:
                strength = 0.80
                result.evidence_details["app_running"] = True
                self._log(f"  LM Studio app process found: PID {p.pid}", verbose)
            else:
                strength = max(strength, 0.50)
                self._log(f"  LM Studio-related process: PID {p.pid}", verbose)

            info = get_process_info(p.pid)
            if info:
                result.evidence_details["process_detail"] = (
                    f"{info.pid} {info.ppid} {info.username} {info.cmdline}"
                )
                if info.username:
                    result.evidence_details["process_user"] = info.username

        if strength == 0.0:
            self._log("No LM Studio process found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for app installation, data directory, and downloaded model files."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        install_dir = self._paths.install_dir
        app_support_dir = self._paths.config_dir

        if install_dir and install_dir.is_dir():
            strength = 0.55
            result.evidence_details["app_installed"] = True
            self._log(f"  LM Studio app found at {install_dir}", verbose)

        if app_support_dir and app_support_dir.is_dir():
            strength = max(strength, 0.65)
            result.evidence_details["app_support_dir"] = True
            self._log(f"  App support directory found: {app_support_dir}", verbose)

            try:
                file_count = sum(1 for f in app_support_dir.rglob("*") if f.is_file())
                total_size = sum(f.stat().st_size for f in app_support_dir.rglob("*") if f.is_file())
                result.evidence_details["app_support_stats"] = {
                    "file_count": file_count,
                    "total_size_bytes": total_size,
                }
                self._log(f"  {file_count} files, {total_size:,} bytes in app support", verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not count files in LM Studio app support dir %s: %s", app_support_dir, exc)

            # Look for model configuration to find model storage path
            settings_candidates = [
                app_support_dir / "User" / "settings.json",
                app_support_dir / "settings.json",
                app_support_dir / "user-settings.json",
            ]
            for settings_path in settings_candidates:
                if settings_path.is_file():
                    try:
                        data = json.loads(settings_path.read_text())
                        if isinstance(data, dict):
                            model_path = data.get("modelPath") or data.get("model_path")
                            if model_path:
                                result.evidence_details["configured_model_path"] = model_path
                                self._log(f"  Configured model path: {model_path}", verbose)
                                self._scan_model_dir(Path(model_path), result, verbose)
                    except (json.JSONDecodeError, OSError) as exc:
                        logger.debug("Could not read LM Studio settings %s: %s", settings_path, exc)
                    break

        # Default model storage paths
        home = Path.home()
        default_model_dirs = [
            home / ".lmstudio" / "models",
            home / ".cache" / "lm-studio" / "models",
        ]
        if app_support_dir:
            default_model_dirs.append(app_support_dir / "models")
        for model_dir in default_model_dirs:
            if model_dir.is_dir():
                self._scan_model_dir(model_dir, result, verbose)
                if result.evidence_details.get("model_file_count", 0) > 0:
                    break

        if result.evidence_details.get("model_file_count", 0) > 0:
            strength = max(strength, 0.85)

        return strength

    def _scan_model_dir(self, model_dir: Path, result: ScanResult, verbose: bool) -> None:
        """Scan a directory for model files (GGUF, safetensors, etc.)."""
        try:
            model_files = [
                f for f in model_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in MODEL_EXTENSIONS
            ]
            if model_files:
                total_size = sum(f.stat().st_size for f in model_files)
                result.evidence_details["model_file_count"] = len(model_files)
                result.evidence_details["model_storage_path"] = str(model_dir)
                result.evidence_details["model_total_size_bytes"] = total_size
                result.evidence_details["model_names"] = [f.name for f in model_files[:10]]
                size_gb = total_size / (1024 ** 3)
                self._log(
                    f"  {len(model_files)} model file(s), {size_gb:.1f} GB in {model_dir}",
                    verbose,
                )
        except (PermissionError, OSError) as exc:
            self._log(f"  Error scanning model dir {model_dir}: {exc}", verbose)

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for localhost:1234 listener (local server mode)."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        listeners = get_listeners(port=LOCAL_API_PORT)
        if listeners:
            c = listeners[0]
            strength = 0.70
            result.evidence_details["local_server_listener"] = (
                f"{c.local_addr}:{c.local_port} LISTEN"
            )
            result.evidence_details["local_server_active"] = True
            if c.pid is not None:
                result.evidence_details["server_pid"] = c.pid
            self._log(f"  LM Studio local server listener on :{LOCAL_API_PORT}", verbose)

        if strength > 0:
            api_response = self._query_api(
                f"http://localhost:{LOCAL_API_PORT}/v1/models", verbose
            )
            if api_response:
                try:
                    data = json.loads(api_response)
                    models = data.get("data", [])
                    if models:
                        result.evidence_details["api_models"] = [
                            m.get("id") for m in models[:10]
                        ]
                        strength = 0.85
                        self._log(f"  API reports {len(models)} loaded model(s)", verbose)
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.debug("Could not parse LM Studio API models response: %s", exc)

        if strength == 0.0:
            self._log(f"  No listener on :{LOCAL_API_PORT}", verbose)

        return strength

    def _query_api(self, url: str, verbose: bool) -> str | None:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            self._log(f"  API query failed ({url}): {exc}", verbose)
            return None

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user and process ownership."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.40
            result.evidence_details["identity_user"] = process_user
            self._log(f"  Process owner: {process_user}", verbose)
        elif (
            (self._paths.config_dir and self._paths.config_dir.is_dir())
            or (self._paths.install_dir and self._paths.install_dir.is_dir())
        ):
            import getpass
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.30

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for active inference and recent model activity."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        app_running = result.evidence_details.get("app_running", False)
        has_models = result.evidence_details.get("model_file_count", 0) > 0
        server_active = result.evidence_details.get("local_server_active", False)

        if server_active and has_models:
            strength = 0.80
            result.evidence_details["active_inference_capable"] = True
            self._log("  Local server + models loaded = active inference capable", verbose)
        elif app_running and has_models:
            strength = 0.65
            self._log("  App running with models present", verbose)
        elif app_running:
            strength = 0.45
        elif has_models:
            strength = 0.35

        # Check recent model file access
        model_path_str = result.evidence_details.get("model_storage_path")
        if model_path_str:
            model_path = Path(model_path_str)
            now = time.time()
            try:
                recent = [
                    f for f in model_path.rglob("*")
                    if f.is_file() and (now - f.stat().st_mtime) < 86400
                    and f.suffix.lower() in MODEL_EXTENSIONS
                ]
                if recent:
                    result.evidence_details["recent_model_access"] = len(recent)
                    strength = max(strength, 0.60)
                    self._log(f"  {len(recent)} model file(s) accessed in last 24h", verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not check recent model file access in %s: %s", model_path, exc)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        self._penalize_missing_process_chain(result, "app_running", amount=0.10)
        self._penalize_stale_artifacts(result, amount=0.10, require_no_network=True)
        self._penalize_weak_identity(result, threshold=0.4, amount=0.10)

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("local_server_active"):
            summaries.append("LM Studio local server active on :1234 (unauthenticated API)")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("app_running"):
            summaries.append("LM Studio application running")
            result.action_type = "exec"
            result.action_risk = "R1"
        elif result.evidence_details.get("app_installed"):
            summaries.append("LM Studio installed")
            result.action_type = "read"
            result.action_risk = "R1"

        count = result.evidence_details.get("model_file_count", 0)
        size_bytes = result.evidence_details.get("model_total_size_bytes", 0)
        if count > 0:
            size_gb = size_bytes / (1024 ** 3)
            summaries.append(f"{count} model file(s) ({size_gb:.1f} GB)")

        model_names = result.evidence_details.get("model_names", [])
        if model_names:
            summaries.append(f"models: {', '.join(model_names[:3])}")

        api_models = result.evidence_details.get("api_models", [])
        if api_models:
            summaries.append(f"loaded via API: {', '.join(str(m) for m in api_models[:3])}")

        result.action_summary = "; ".join(summaries) if summaries else "No LM Studio signals detected"
