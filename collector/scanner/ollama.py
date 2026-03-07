"""Ollama detection module (Class B -- Local Model Runtime)."""

from __future__ import annotations

import getpass
import logging
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from compat import (
    find_processes,
    get_listeners,
    get_service,
    get_tool_paths,
    user_exists,
    ToolPaths,
)

from .base import BaseScanner, LayerSignals, ScanResult
from .constants import OLLAMA_API_PORT

logger = logging.getLogger(__name__)


class OllamaScanner(BaseScanner):
    """Detects Ollama daemon, model storage, and API listener via five-layer signal model."""

    def __init__(self) -> None:
        self._paths: ToolPaths = get_tool_paths("ollama")

    @property
    def tool_name(self) -> str:
        return "Ollama"

    @property
    def tool_class(self) -> str:
        return "B"

    def scan(self, verbose: bool = False) -> ScanResult:
        self._paths = get_tool_paths("ollama")
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
        """Detect Ollama version via ollama --version (version may be on stdout or stderr)."""
        proc = self._run_cmd(["ollama", "--version"], timeout=5)
        if not proc:
            return None
        combined = (proc.stdout or "").strip() + "\n" + (proc.stderr or "").strip()
        if not combined:
            return None
        match = re.search(r"(\d+\.\d+\.\d+)", combined)
        if match:
            version = match.group(1)
            self._log(f"Version from CLI: {version}", verbose)
            return version
        first_line = combined.splitlines()[0].strip() if combined else ""
        if first_line:
            self._log(f"Version from CLI: {first_line}", verbose)
            return first_line
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for ollama daemon and CLI processes."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        procs = find_processes(r"\bollama\b")
        procs = [p for p in procs if "collector" not in p.cmdline.lower()]

        if procs:
            for p in procs:
                result.evidence_details.setdefault("process_entries", []).append({
                    "pid": p.pid, "cmdline": p.cmdline,
                })

                if "serve" in p.cmdline:
                    strength = 0.85
                    result.evidence_details["daemon_running"] = True
                    self._log(f"  Daemon found: PID {p.pid}", verbose)
                else:
                    strength = max(strength, 0.6)
                    self._log(f"  CLI process found: PID {p.pid} ({p.cmdline})", verbose)

                if p.username:
                    result.evidence_details["process_user"] = p.username
                result.evidence_details["process_detail"] = (
                    f"PID={p.pid} PPID={p.ppid} USER={p.username} CMD={p.cmdline}"
                )

        svc = get_service("ollama")
        if svc:
            svc_desc = f"{svc.name} status={svc.status} start={svc.start_type}"
            result.evidence_details["managed_service"] = svc_desc
            if strength == 0.0:
                strength = 0.3
            self._log(f"  Managed service: {svc_desc}", verbose)

        if strength == 0.0:
            self._log("No ollama process found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for Ollama data directory, model storage, and keypair."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0
        ollama_dir = self._paths.data_dir

        if ollama_dir is None or not ollama_dir.is_dir():
            self._log("No Ollama data directory found", verbose)
            return strength

        strength = 0.5
        self._log(f"Found {ollama_dir}", verbose)

        models_dir = ollama_dir / "models"
        if models_dir.is_dir():
            strength = 0.7
            try:
                file_count = sum(1 for _ in models_dir.rglob("*") if _.is_file())
                total_size = sum(f.stat().st_size for f in models_dir.rglob("*") if f.is_file())
                result.evidence_details["models_dir"] = {
                    "file_count": file_count,
                    "total_size_bytes": total_size,
                }
                self._log(f"  Models: {file_count} files, {total_size:,} bytes", verbose)

                if file_count > 0:
                    strength = 0.85

                model_names = self._parse_model_manifests(models_dir)
                if model_names:
                    result.evidence_details["model_names"] = model_names
                    strength = 0.90
                    self._log(f"  Models found: {model_names}", verbose)

            except (PermissionError, OSError) as exc:
                self._log(f"  Error reading models dir: {exc}", verbose)

        keypair = ollama_dir / "id_ed25519"
        if keypair.is_file():
            result.evidence_details["ed25519_keypair"] = True
            strength = max(strength, 0.7)
            self._log("  Ed25519 keypair found (tool has been run)", verbose)

        return strength

    def _parse_model_manifests(self, models_dir: Path) -> list[str]:
        """Extract model names from the OCI manifest directory structure."""
        names: list[str] = []
        manifests_root = models_dir / "manifests" / "registry.ollama.ai" / "library"
        if not manifests_root.is_dir():
            return names
        for model_dir in manifests_root.iterdir():
            if model_dir.is_dir():
                for tag_file in model_dir.iterdir():
                    if tag_file.is_file():
                        names.append(f"{model_dir.name}:{tag_file.name}")
        return names

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for localhost listener and query the Ollama API."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        listeners = get_listeners(port=OLLAMA_API_PORT)
        if listeners:
            listener = listeners[0]
            strength = 0.7
            result.evidence_details[f"port_{OLLAMA_API_PORT}_listener"] = (
                f"{listener.local_addr}:{listener.local_port} (PID {listener.pid})"
            )
            if listener.pid is not None:
                result.evidence_details["listener_pid"] = listener.pid
            self._log(f"  Port {OLLAMA_API_PORT} listener found", verbose)

        if strength > 0:
            health = self._query_api(f"http://localhost:{OLLAMA_API_PORT}/", verbose)
            if health:
                result.evidence_details["api_health"] = health
                strength = max(strength, 0.75)

            tags = self._query_api(f"http://localhost:{OLLAMA_API_PORT}/api/tags", verbose)
            if tags:
                try:
                    tag_data = json.loads(tags)
                    models = tag_data.get("models", [])
                    result.evidence_details["api_model_inventory"] = [
                        {
                            "name": m.get("name"),
                            "size": m.get("size"),
                            "digest": m.get("digest", "")[:16],
                        }
                        for m in models
                    ]
                    self._log(f"  API reports {len(models)} model(s)", verbose)
                    if models:
                        strength = 0.85
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.debug("Could not parse Ollama API tags response: %s", exc)

        ollama_host = os.environ.get("OLLAMA_HOST", "")
        if "0.0.0.0" in ollama_host:
            result.evidence_details["network_exposed"] = True
            result.evidence_details["ollama_host_env"] = ollama_host
            strength = max(strength, 0.5)
            self._log("  WARNING: OLLAMA_HOST bound to 0.0.0.0 (network-exposed)", verbose)

        if strength == 0.0:
            self._log(f"  No port {OLLAMA_API_PORT} listener found", verbose)

        return strength

    def _query_api(self, url: str, verbose: bool) -> str | None:
        """Query Ollama's unauthenticated localhost API."""
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return body
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            self._log(f"  API query failed ({url}): {exc}", verbose)
            return None

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user ownership and dedicated system user."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.4
            result.evidence_details["identity_user"] = process_user
            self._log(f"  Process owner: {process_user}", verbose)

        if user_exists("ollama"):
            result.evidence_details["dedicated_ollama_user"] = True
            strength = max(strength, 0.5)
            self._log("  Dedicated ollama system user exists", verbose)

        data_dir = self._paths.data_dir
        if strength == 0 and data_dir and data_dir.is_dir():
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.3

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for active inference capability and recent model activity."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        daemon_running = result.evidence_details.get("daemon_running", False)
        has_models = bool(result.evidence_details.get("model_names") or
                          result.evidence_details.get("api_model_inventory"))

        if daemon_running and has_models:
            strength = 0.8
            result.evidence_details["active_inference_capable"] = True
            self._log("  Daemon running + models loaded = active inference capability", verbose)
        elif daemon_running:
            strength = 0.5
            self._log("  Daemon running but no models detected", verbose)
        elif has_models:
            strength = 0.4
            self._log("  Models present but daemon not running", verbose)

        data_dir = self._paths.data_dir
        if data_dir:
            models_dir = data_dir / "models"
            if models_dir.is_dir():
                now = time.time()
                recent_threshold = 86400  # 24 hours
                try:
                    recent = [
                        f for f in models_dir.rglob("*")
                        if f.is_file() and (now - f.stat().st_mtime) < recent_threshold
                    ]
                    if recent:
                        result.evidence_details["recent_model_activity"] = len(recent)
                        strength = max(strength, 0.6)
                        self._log(f"  {len(recent)} model files modified in last 24h", verbose)
                except (PermissionError, OSError) as exc:
                    logger.debug("Could not check recent model files in %s: %s", models_dir, exc)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalty conditions from Appendix B."""
        self._penalize_missing_process_chain(result, "daemon_running", amount=0.15)

        if result.signals.network > 0 and result.signals.process > 0:
            listener_pid = result.evidence_details.get("listener_pid")
            process_pids = [
                e.get("pid") for e in result.evidence_details.get("process_entries", [])
            ]
            if listener_pid and listener_pid not in process_pids:
                result.penalties.append(("unresolved_process_network_linkage", 0.10))

        self._penalize_stale_artifacts(result, amount=0.10, require_no_network=True)
        self._penalize_weak_identity(result, threshold=0.4, amount=0.10)

        if result.evidence_details.get("network_exposed"):
            result.action_risk = "R3"

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("daemon_running"):
            summaries.append("Ollama daemon running")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("managed_service"):
            summaries.append("Ollama registered as managed service")
            result.action_type = "exec"

        models_info = result.evidence_details.get("models_dir", {})
        if models_info:
            size_mb = models_info.get("total_size_bytes", 0) / (1024 * 1024)
            count = models_info.get("file_count", 0)
            summaries.append(f"~/.ollama/models/ with {count} files ({size_mb:.0f} MB)")

        model_names = result.evidence_details.get("model_names", [])
        api_models = result.evidence_details.get("api_model_inventory", [])
        all_models = model_names or [m.get("name", "") for m in api_models]
        if all_models:
            summaries.append(f"Models: {', '.join(all_models[:5])}")

        if result.evidence_details.get("ed25519_keypair"):
            summaries.append("ed25519 keypair present (tool has been run)")

        if result.evidence_details.get(f"port_{OLLAMA_API_PORT}_listener"):
            summaries.append(f"localhost:{OLLAMA_API_PORT} listener (unauthenticated API)")

        if result.evidence_details.get("network_exposed"):
            summaries.append("WARNING: API bound to 0.0.0.0 (network-exposed)")
            result.action_risk = "R3"

        if result.evidence_details.get("active_inference_capable"):
            summaries.append("active inference capability confirmed")

        result.action_summary = "; ".join(summaries) if summaries else "No Ollama signals detected"
