"""Open Interpreter detection module (Class C — Autonomous Executor).

Open Interpreter is a Python CLI tool that executes LLM-generated code via a Jupyter
kernel. It runs as a generic `python3` process (not a distinctive binary), stores zero
persistent state outside its virtualenv, and relies on behavior-anchored detection.
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from .base import BaseScanner, LayerSignals, ScanResult

SEARCH_DEPTH = 6
VENV_SEARCH_TIMEOUT = 10

DISTINCTIVE_DEPS = {"litellm", "anthropic", "openai"}


class OpenInterpreterScanner(BaseScanner):
    """Detects Open Interpreter via five-layer signal model with behavior as primary anchor."""

    @property
    def tool_name(self) -> str:
        return "Open Interpreter"

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
        """Detect Open Interpreter version via CLI or pip show."""
        proc = self._run_cmd(["open-interpreter", "--version"], timeout=5)
        if proc and proc.returncode == 0 and proc.stdout.strip():
            version = proc.stdout.strip()
            if version:
                self._log(f"Version from CLI: {version}", verbose)
                return version
        proc = self._run_cmd(["pip", "show", "open-interpreter"], timeout=10)
        if proc and proc.returncode == 0 and proc.stdout.strip():
            for line in proc.stdout.splitlines():
                if line.strip().lower().startswith("version:"):
                    version = line.split(":", 1)[1].strip()
                    if version:
                        self._log(f"Version from pip show: {version}", verbose)
                        return version
                    break
        return None

    def _scan_process(self, result: ScanResult, verbose: bool) -> float:
        """Check for Python processes with interpreter module paths and ipykernel children."""
        self._log("Scanning process layer...", verbose)
        strength = 0.0

        proc = self._run_cmd(["pgrep", "-fl", "interpreter"])
        if not (proc and proc.returncode == 0 and proc.stdout.strip()):
            self._log("No interpreter-related process found", verbose)
            return strength

        interpreter_pids: list[str] = []
        for line in proc.stdout.strip().splitlines():
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            pid, cmdline = parts
            if "pgrep" in cmdline.lower():
                continue
            if "collector" in cmdline.lower() or "agentic-governance" in cmdline.lower():
                continue
            if re.search(r'interpreter', cmdline, re.IGNORECASE):
                interpreter_pids.append(pid)
                result.evidence_details.setdefault("process_entries", []).append({
                    "pid": pid, "cmdline": cmdline,
                })

        if not interpreter_pids:
            self._log("No interpreter-related process found (after filtering)", verbose)
            return strength

        strength = 0.60
        self._log(f"Found interpreter process(es): {interpreter_pids}", verbose)

        ipykernel_found = False
        for pid in interpreter_pids[:5]:
            children = self._run_cmd(["pgrep", "-P", pid])
            if not (children and children.returncode == 0 and children.stdout.strip()):
                continue

            for cpid in children.stdout.strip().splitlines()[:10]:
                child_info = self._run_cmd(["ps", "-p", cpid, "-o", "pid,command"])
                if not (child_info and child_info.returncode == 0):
                    continue
                child_cmd = child_info.stdout.strip()

                if "ipykernel" in child_cmd:
                    ipykernel_found = True
                    result.evidence_details["ipykernel_pid"] = cpid
                    result.evidence_details.setdefault("child_processes", []).append(child_cmd)
                    self._log(f"  ipykernel child found: PID {cpid}", verbose)

                    kernel_children = self._run_cmd(["pgrep", "-P", cpid])
                    if kernel_children and kernel_children.returncode == 0 and kernel_children.stdout.strip():
                        for kcpid in kernel_children.stdout.strip().splitlines()[:10]:
                            kc_info = self._run_cmd(["ps", "-p", kcpid, "-o", "pid,command"])
                            if kc_info and kc_info.returncode == 0:
                                kc_cmd = kc_info.stdout.strip()
                                if re.search(r'(bash|sh|pip|pytest|python|git)', kc_cmd):
                                    result.evidence_details.setdefault(
                                        "agentic_children", []
                                    ).append(kc_cmd)

        if ipykernel_found:
            strength = 0.70
            self._log("  python → ipykernel chain confirmed", verbose)

        detail = self._run_cmd(["ps", "-p", interpreter_pids[0], "-o", "pid,ppid,user,command"])
        if detail and detail.returncode == 0:
            result.evidence_details["process_detail"] = detail.stdout.strip()
            for dl in detail.stdout.splitlines()[1:]:
                fields = dl.split()
                if len(fields) >= 3:
                    result.evidence_details["process_user"] = fields[2]

        return strength

    def _scan_file(self, result: ScanResult, verbose: bool) -> float:
        """Search for open-interpreter package in venvs and check dependency fingerprint."""
        self._log("Scanning file layer...", verbose)
        strength = 0.0

        interpreter_paths = self._find_interpreter_packages(verbose)
        if not interpreter_paths:
            self._log("  No interpreter package found in site-packages", verbose)
            return strength

        strength = 0.65
        result.evidence_details["interpreter_install_paths"] = [str(p) for p in interpreter_paths]
        self._log(f"  Found interpreter package in {len(interpreter_paths)} location(s)", verbose)

        for pkg_path in interpreter_paths[:3]:
            site_packages = pkg_path.parent
            deps_found: list[str] = []
            for dep_name in DISTINCTIVE_DEPS:
                dep_dir = site_packages / dep_name
                if dep_dir.is_dir():
                    deps_found.append(dep_name)

            if len(deps_found) >= len(DISTINCTIVE_DEPS):
                strength = 0.80
                result.evidence_details["dependency_fingerprint"] = deps_found
                self._log(
                    f"  Full dependency fingerprint: {', '.join(deps_found)}", verbose,
                )
                break
            elif deps_found:
                strength = max(strength, 0.70)
                result.evidence_details["partial_dependency_fingerprint"] = deps_found

        for config_path in [
            Path.home() / ".config" / "open-interpreter",
            Path.home() / ".local" / "share" / "open-interpreter",
        ]:
            if config_path.is_dir():
                result.evidence_details["config_dir"] = str(config_path)
                strength = max(strength, 0.70)
                self._log(f"  Config directory found: {config_path}", verbose)

        return strength

    def _find_interpreter_packages(self, verbose: bool) -> list[Path]:
        """Search bounded locations for interpreter package in site-packages."""
        results: list[Path] = []

        find = self._run_cmd(
            [
                "find", str(Path.home()),
                "-maxdepth", str(SEARCH_DEPTH),
                "-path", "*/site-packages/interpreter/__init__.py",
                "-not", "-path", "*/agentic-governance/*",
            ],
            timeout=VENV_SEARCH_TIMEOUT,
        )
        if find and find.returncode == 0 and find.stdout.strip():
            for line in find.stdout.strip().splitlines():
                pkg_dir = Path(line).parent
                if pkg_dir.is_dir():
                    results.append(pkg_dir)

        return results

    def _scan_network(self, result: ScanResult, verbose: bool) -> float:
        """Check for network connections from interpreter processes to known LLM endpoints."""
        self._log("Scanning network layer...", verbose)
        strength = 0.0

        interpreter_pids = {
            e["pid"] for e in result.evidence_details.get("process_entries", [])
        }
        ipykernel_pid = result.evidence_details.get("ipykernel_pid")
        if ipykernel_pid:
            interpreter_pids.add(ipykernel_pid)

        if not interpreter_pids:
            return strength

        lsof = self._run_cmd(["lsof", "-i", "-n", "-P"])
        if not (lsof and lsof.returncode == 0):
            self._log("  lsof failed or unavailable", verbose)
            return strength

        known_llm_patterns = [
            "api.openai.com", "api.anthropic.com",
            ":11434", ":8080", ":4000",
        ]

        connections: list[str] = []
        llm_connections: list[str] = []
        for line in lsof.stdout.splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            if parts[1] not in interpreter_pids:
                continue
            if "ESTABLISHED" in line or "LISTEN" in line:
                connections.append(line.strip())
                for pattern in known_llm_patterns:
                    if pattern in line:
                        llm_connections.append(line.strip())
                        break

        if llm_connections:
            strength = 0.55
            result.evidence_details["llm_endpoint_connections"] = llm_connections[:10]
            self._log(f"  {len(llm_connections)} connection(s) to known LLM endpoints", verbose)
        elif connections:
            strength = 0.40
            result.evidence_details["unresolved_connections"] = len(connections)
            self._log(
                f"  {len(connections)} connection(s) found but destination unclear", verbose,
            )

        for env_var in ("OLLAMA_HOST", "OPENAI_API_BASE"):
            val = os.environ.get(env_var)
            if val:
                result.evidence_details.setdefault("model_routing_env", {})[env_var] = val
                self._log(f"  {env_var}={val} (custom model routing)", verbose)

        return strength

    def _scan_identity(self, result: ScanResult, verbose: bool) -> float:
        """Check OS user and environment for API credentials."""
        self._log("Scanning identity layer...", verbose)
        strength = 0.0

        process_user = result.evidence_details.get("process_user")
        if process_user:
            strength = 0.30
            result.evidence_details["identity_user"] = process_user
            self._log(f"  Process owner: {process_user}", verbose)
        elif result.evidence_details.get("interpreter_install_paths"):
            import getpass
            result.evidence_details["identity_user"] = getpass.getuser()
            strength = 0.30

        api_keys_found: list[str] = []
        for key_name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if os.environ.get(key_name):
                api_keys_found.append(key_name)

        if api_keys_found:
            strength = 0.60
            result.evidence_details["api_keys_present"] = api_keys_found
            self._log(f"  API key(s) in environment: {', '.join(api_keys_found)}", verbose)

        return strength

    def _scan_behavior(self, result: ScanResult, verbose: bool) -> float:
        """Check for agentic command-chain patterns — the primary detection anchor."""
        self._log("Scanning behavior layer...", verbose)
        strength = 0.0
        auto_run_detected = False

        ipykernel_pid = result.evidence_details.get("ipykernel_pid")
        agentic_children = result.evidence_details.get("agentic_children", [])

        if ipykernel_pid and agentic_children:
            strength = 0.85
            self._log("  ipykernel + shell command chain confirmed", verbose)

        for entry in result.evidence_details.get("process_entries", []):
            cmdline = entry.get("cmdline", "")
            if re.search(r'(auto_run|--?y\b)', cmdline):
                auto_run_detected = True
                result.evidence_details["auto_run_detected"] = True
                self._log("  auto_run / -y flag detected (no safety confirmations)", verbose)
                break

        if auto_run_detected and strength >= 0.85:
            strength = 0.90
        elif auto_run_detected:
            strength = max(strength, 0.70)

        if agentic_children:
            rapid_tools = {"pip", "pytest", "python", "git", "npm", "bash"}
            child_tools_found = set()
            for child_cmd in agentic_children:
                for tool in rapid_tools:
                    if tool in child_cmd.lower():
                        child_tools_found.add(tool)
            if len(child_tools_found) >= 2:
                strength = max(strength, 0.85)
                result.evidence_details["command_chain_tools"] = list(child_tools_found)
                self._log(
                    f"  Rapid command chain: {', '.join(child_tools_found)}", verbose,
                )

        if (
            strength == 0.0
            and result.evidence_details.get("interpreter_install_paths")
            and result.evidence_details.get("dependency_fingerprint")
        ):
            strength = 0.40
            self._log("  Installed with full deps but not running", verbose)

        if auto_run_detected:
            result.evasion_boost += 0.10

        return strength

    def _apply_penalties(self, result: ScanResult) -> None:
        """Apply confidence penalties per Appendix B."""
        if result.evidence_details.get("interpreter_install_paths"):
            result.penalties.append(("non_default_artifact_paths", 0.05))

        interpreter_pids = {
            e["pid"] for e in result.evidence_details.get("process_entries", [])
        }
        if interpreter_pids and not result.evidence_details.get("llm_endpoint_connections"):
            result.penalties.append(("unresolved_process_network_linkage", 0.05))

        self._penalize_weak_identity(result, threshold=0.5, amount=0.05)

    def _determine_action(self, result: ScanResult) -> None:
        """Set action type, risk class, and summary based on findings."""
        summaries: list[str] = []

        auto_run = result.evidence_details.get("auto_run_detected", False)
        agentic_children = result.evidence_details.get("agentic_children", [])

        if auto_run and agentic_children:
            summaries.append("Open Interpreter running with auto_run + shell children")
            result.action_type = "exec"
            result.action_risk = "R3"
        elif result.evidence_details.get("process_entries"):
            summaries.append("Open Interpreter process detected")
            result.action_type = "exec"
            result.action_risk = "R2"
        elif result.evidence_details.get("interpreter_install_paths"):
            summaries.append("Open Interpreter installed (not running)")
            result.action_type = "read"
            result.action_risk = "R1"

        install_paths = result.evidence_details.get("interpreter_install_paths", [])
        if install_paths:
            summaries.append(f"installed in {len(install_paths)} location(s)")

        if result.evidence_details.get("dependency_fingerprint"):
            deps = result.evidence_details["dependency_fingerprint"]
            summaries.append(f"dependency fingerprint: {', '.join(deps)}")

        if result.evidence_details.get("ipykernel_pid"):
            summaries.append("Jupyter kernel execution substrate active")

        if auto_run:
            summaries.append("WARNING: auto_run enabled (no safety confirmations)")

        if result.evidence_details.get("command_chain_tools"):
            tools = result.evidence_details["command_chain_tools"]
            summaries.append(f"command chain: {', '.join(tools)}")

        if result.evidence_details.get("api_keys_present"):
            keys = result.evidence_details["api_keys_present"]
            summaries.append(f"API keys in env: {', '.join(keys)}")

        result.action_summary = (
            "; ".join(summaries) if summaries else "No Open Interpreter signals detected"
        )
