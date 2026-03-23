"""Continue IDE extension detection module (Class A — Assistive IDE Extension).

Continue is a backend-agnostic AI coding assistant that runs as a VS Code / Cursor
extension. It has no distinctive binary; detection anchors on:
  1. ~/.continue/config.json or config.yaml (primary — reveals backend routing)
  2. Extension manifest in VS Code or Cursor extensions directory
  3. Task history / cache artifacts in extension globalStorage
  4. Extension host network traffic (backend-dependent destination)

Risk escalates from Class A to higher risk posture when config routes to an
unapproved backend or when the extension is used with sensitive repository context.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

from compat import find_processes, get_connections, get_tool_paths

from .base import BaseScanner, LayerSignals, ScanResult

logger = logging.getLogger(__name__)
CONTINUE_DIR = Path.home() / ".continue"

KNOWN_UNAPPROVED_BACKENDS = frozenset({
    "ollama", "lmstudio", "llamafile", "lm-studio",
    "together", "perplexity", "groq",
})


def _all_ext_dirs() -> list[Path]:
    vscode = get_tool_paths("vscode")
    cursor = get_tool_paths("cursor")
    dirs: list[Path] = []
    if vscode.extensions_dir:
        dirs.append(vscode.extensions_dir)
    if vscode.config_dir:
        dirs.append(vscode.config_dir / "User" / "extensions")
    if cursor.extensions_dir:
        dirs.append(cursor.extensions_dir)
    if cursor.config_dir:
        dirs.append(cursor.config_dir / "User" / "extensions")
    return dirs


def _storage_roots() -> list[Path]:
    vscode = get_tool_paths("vscode")
    cursor = get_tool_paths("cursor")
    roots: list[Path] = []
    if vscode.config_dir:
        roots.append(vscode.config_dir / "User" / "globalStorage")
    if cursor.config_dir:
        roots.append(cursor.config_dir / "User" / "globalStorage")
    return roots


class ContinueScanner(BaseScanner):
    """Detects Continue IDE extension via five-layer signal model."""

    @property
    def tool_name(self) -> str:
        return "Continue"

    @property
    def tool_class(self) -> str:
        return "A"

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
            result.process_patterns = ["continue"]

        return result

    def _detect_version(self, verbose: bool) -> str | None:
        """Detect Continue extension version from extension manifest."""
        for ext_dir in _all_ext_dirs():
            if not ext_dir.is_dir():
                continue
            try:
                for entry in ext_dir.iterdir():
                    if not entry.is_dir():
                        continue
                    if re.match(r'continue\.continue-', entry.name, re.IGNORECASE):
                        pkg = entry / "package.json"
                        if pkg.is_file():
                            try:
                                data = json.loads(pkg.read_text())
                                version = data.get("version")
                                if version:
                                    self._log(f"Version from extension manifest: {version}", verbose)
                                    return str(version)
                            except (json.JSONDecodeError, OSError) as exc:
                                logger.debug("Could not read Continue package.json %s: %s", pkg, exc)
            except (PermissionError, OSError):
                continue
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for IDE extension host processes associated with Continue activity."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        for ide_name in ("Code", "Cursor"):
            procs = find_processes(ide_name)
            procs = [
                p for p in procs
                if "collector" not in p.cmdline.lower()
                and ("extensionHost" in p.cmdline or "extension-host" in p.cmdline)
            ]
            for p in procs:
                result.evidence_details.setdefault("ide_extension_hosts", []).append({
                    "ide": ide_name, "pid": p.pid,
                })
                strength = max(strength, 0.30)
                self._log(f"  {ide_name} extension host found: PID {p.pid}", verbose)

        if strength > 0 and result.evidence_details.get("ide_extension_hosts"):
            self._log(f"  {len(result.evidence_details['ide_extension_hosts'])} extension host(s)", verbose)
        else:
            self._log("  No extension host process found", verbose)

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Check for Continue config directory, extension manifests, and task artifacts."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        # Primary anchor: ~/.continue/ directory with config
        if CONTINUE_DIR.is_dir():
            strength = 0.55
            self._log(f"Found {CONTINUE_DIR}", verbose)

            try:
                file_count = sum(1 for f in CONTINUE_DIR.rglob("*") if f.is_file())
                result.evidence_details["continue_dir"] = {"file_count": file_count}
                self._log(f"  {file_count} files in ~/.continue/", verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not count files in ~/.continue/: %s", exc)

            for config_name in ("config.json", "config.yaml", "config.yml"):
                config_path = CONTINUE_DIR / config_name
                if config_path.is_file():
                    strength = 0.80
                    result.evidence_details["config_file"] = str(config_path)
                    self._log(f"  Config found: {config_path.name}", verbose)
                    self._analyze_config(config_path, result, verbose)
                    break

        # Extension manifests in VS Code / Cursor
        ext_installs: list[dict[str, str]] = []
        for ext_dir in _all_ext_dirs():
            if not ext_dir.is_dir():
                continue
            try:
                for entry in ext_dir.iterdir():
                    if not entry.is_dir():
                        continue
                    if re.match(r'continue\.continue-', entry.name, re.IGNORECASE):
                        ide_label = "Cursor" if "Cursor" in str(ext_dir) else "VSCode"
                        ext_installs.append({"ide": ide_label, "dir": entry.name})
                        self._log(f"  Extension found: {entry.name} ({ide_label})", verbose)
            except (PermissionError, OSError):
                continue

        if ext_installs:
            strength = max(strength, 0.70)
            result.evidence_details["extension_installs"] = ext_installs

        # Task history in globalStorage
        task_counts = 0
        for storage_root in _storage_roots():
            storage = storage_root / "continue.continue"
            if storage.is_dir():
                try:
                    files = list(storage.rglob("*"))
                    task_counts += sum(1 for f in files if f.is_file())
                    result.evidence_details["global_storage_dir"] = str(storage)
                    strength = max(strength, 0.75)
                    self._log(f"  GlobalStorage found: {storage}", verbose)
                except (PermissionError, OSError) as exc:
                    logger.debug("Could not list Continue globalStorage %s: %s", storage, exc)

        if task_counts > 0:
            result.evidence_details["task_file_count"] = task_counts

        return strength

    def _analyze_config(self, config_path: Path, result: ScanResult, verbose: bool) -> None:
        """Parse Continue config to identify backend routing and risk escalation."""
        try:
            content = config_path.read_text(encoding="utf-8")
            if config_path.suffix in (".yaml", ".yml"):
                result.evidence_details["config_format"] = "yaml"
                return
            data = json.loads(content)
        except (json.JSONDecodeError, PermissionError, OSError, UnicodeDecodeError):
            return

        if not isinstance(data, dict):
            return

        models = data.get("models", [])
        backends_found: list[str] = []
        for model in (models if isinstance(models, list) else []):
            if not isinstance(model, dict):
                continue
            provider = model.get("provider", "").lower()
            if provider:
                backends_found.append(provider)

        if backends_found:
            result.evidence_details["configured_backends"] = backends_found
            self._log(f"  Backends in config: {', '.join(backends_found)}", verbose)

        unapproved = [b for b in backends_found if any(
            u in b for u in KNOWN_UNAPPROVED_BACKENDS
        )]
        if unapproved:
            result.evidence_details["unapproved_backends"] = unapproved
            result.evasion_boost += 0.10
            self._log(f"  RISK: Unapproved backend(s): {', '.join(unapproved)}", verbose)

        tab_autocomplete = data.get("tabAutocompleteModel")
        if tab_autocomplete:
            result.evidence_details["tab_autocomplete_configured"] = True

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for network connections from extension host PIDs to model endpoints."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        ext_host_pids = {
            e["pid"] for e in result.evidence_details.get("ide_extension_hosts", [])
        }
        if not ext_host_pids:
            self._log("  No extension host PIDs to check", verbose)
            return strength

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if not (lsof and lsof.returncode == 0):
            return strength

        tls_conns: list[str] = []
        local_conns: list[str] = []
        for line in lsof.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2 or parts[1] not in ext_host_pids:
                continue
            if ":443" in line and "ESTABLISHED" in line:
                tls_conns.append(line.strip())
            if (":1234" in line or ":11434" in line) and "ESTABLISHED" in line:
                local_conns.append(line.strip())
                self._log("  Local model server connection from extension host", verbose)

        if local_conns:
            strength = 0.55
            result.evidence_details["local_model_connections"] = local_conns[:5]
            result.evidence_details["unapproved_backend_active"] = True
            self._log(f"  {len(local_conns)} connection(s) to local model server", verbose)
        elif tls_conns:
            strength = 0.40
            result.evidence_details["tls_connections"] = len(tls_conns)
            self._log(f"  {len(tls_conns)} TLS connection(s) from extension host", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user and API key presence in environment."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        import getpass
        result.evidence_details["identity_user"] = getpass.getuser()
        strength = 0.25

        for key_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
            if __import__("os").environ.get(key_name):
                result.evidence_details.setdefault("api_keys_present", []).append(key_name)
                strength = max(strength, 0.45)
                self._log(f"  API key in env: {key_name}", verbose)

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for recent extension activity and unapproved backend usage."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0

        now = time.time()
        recent_threshold = 3600

        if CONTINUE_DIR.is_dir():
            try:
                recent = [
                    f for f in CONTINUE_DIR.rglob("*")
                    if f.is_file() and (now - f.stat().st_mtime) < recent_threshold
                ]
                if recent:
                    strength = max(strength, 0.55)
                    result.evidence_details["recent_continue_files"] = len(recent)
                    self._log(f"  {len(recent)} file(s) modified in last hour", verbose)
            except (PermissionError, OSError) as exc:
                logger.debug("Could not list recent files in ~/.continue/ for behavior scan: %s", exc)

        if result.evidence_details.get("unapproved_backends"):
            strength = max(strength, 0.65)
            self._log("  Configured with unapproved backend (risk escalation)", verbose)

        if result.evidence_details.get("unapproved_backend_active"):
            strength = max(strength, 0.80)
            self._log("  Active connection to unapproved backend", verbose)

        if result.evidence_details.get("tab_autocomplete_configured"):
            strength = max(strength, 0.50)

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        self._penalize_stale_artifacts(result, amount=0.05)
        self._penalize_weak_identity(result, threshold=0.4, amount=0.05)

        if not result.evidence_details.get("config_file"):
            result.penalties.append(("missing_config_anchor", 0.10))

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        if result.evidence_details.get("unapproved_backend_active"):
            summaries.append("Continue routing to unapproved backend (active)")
            result.action_type = "read"
            result.action_risk = "R2"
        elif result.evidence_details.get("unapproved_backends"):
            summaries.append("Continue configured with unapproved backend")
            result.action_type = "read"
            result.action_risk = "R2"
        elif result.evidence_details.get("extension_installs"):
            summaries.append("Continue extension installed")
            result.action_type = "read"
            result.action_risk = "R1"

        installs = result.evidence_details.get("extension_installs", [])
        if installs:
            ides = list({i["ide"] for i in installs})
            summaries.append(f"installed in: {', '.join(ides)}")

        if result.evidence_details.get("config_file"):
            summaries.append("config.json present (backend routing visible)")

        if result.evidence_details.get("configured_backends"):
            backends = result.evidence_details["configured_backends"]
            summaries.append(f"backends: {', '.join(backends[:3])}")

        if result.evidence_details.get("unapproved_backends"):
            unapproved = result.evidence_details["unapproved_backends"]
            summaries.append(f"WARNING: unapproved backend(s): {', '.join(unapproved)}")
            result.action_risk = "R2"

        result.action_summary = "; ".join(summaries) if summaries else "No Continue signals detected"
