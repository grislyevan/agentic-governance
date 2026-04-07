"""New CLI subcommands for the endpoint-first standalone experience.

Provides: status (enhanced), policy, detections, posture, config, doctor.
All commands read local state files only — no API required.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.state import DEFAULT_STATE_DIR as _STATE_DIR


# ── Helpers ──────────────────────────────────────────────────────────


def _read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON file, returning None on any error."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def _find_config_path() -> Path | None:
    """Find the active config file path (collector.json or agent.env)."""
    from config_loader import DEFAULT_CONFIG_PATH, _platform_config_paths

    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    for candidate in _platform_config_paths():
        if candidate.exists():
            return candidate
    return None


def _mask_secret(val: str, visible: int = 8) -> str:
    if len(val) <= visible:
        return val
    return val[:visible] + "..."


def _relative_time(iso_str: str) -> str:
    """Convert ISO timestamp to relative human string."""
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except (ValueError, TypeError):
        return iso_str


# ── detec status (enhanced) ──────────────────────────────────────────


def cmd_status(args: argparse.Namespace) -> None:
    """Show comprehensive agent status."""
    from _version import __version__, __build__

    print(f"Detec Agent v{__version__} (build {__build__})")
    print()

    # Daemon status
    pid_file = _STATE_DIR / "agent.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            alive = _pid_alive(pid)
            if alive:
                print(f"  Daemon         : running (PID {pid})")
            else:
                print(f"  Daemon         : stopped (stale PID file: {pid})")
        except ValueError:
            print("  Daemon         : stopped (corrupt PID file)")
    else:
        print("  Daemon         : not running")

    # Posture
    posture_data = _read_json(_STATE_DIR / "posture.json")
    if posture_data:
        posture = posture_data.get("posture", "unknown")
        source = posture_data.get("source", "unknown")
        threshold = posture_data.get("auto_enforce_threshold", 0.75)
        allow_list = posture_data.get("allow_list", [])
        print(f"  Posture        : {posture} (source: {source})")
        print(f"  Threshold      : {threshold}")
        if allow_list:
            print(f"  Allow-list     : {len(allow_list)} entries")
    else:
        print("  Posture        : passive (default, no state file)")

    # Telemetry provider
    try:
        from providers.registry import get_best_provider

        provider = get_best_provider("auto")
        print(f"  Telemetry      : {provider.name}")
    except Exception:
        print("  Telemetry      : unknown")

    # Last known detections
    state_data = _read_json(_STATE_DIR / "state.json")
    if state_data:
        tools = state_data.get("tools", {})
        active = {k: v for k, v in tools.items() if v.get("detected", False)}
        if active:
            print(f"  Detected tools : {len(active)}")
            for name, info in sorted(active.items()):
                cls = info.get("tool_class", "?")
                conf = info.get("confidence", 0)
                band = info.get("confidence_band", "?")
                decision = info.get("decision_state", "detect")
                print(
                    f"    {name:<24} class={cls}  confidence={conf:.0%} ({band})  decision={decision}"
                )
        else:
            print("  Detected tools : none")
    else:
        print("  Detected tools : no state file (run a scan first)")

    # Server-pushed config
    agent_state = _read_json(_STATE_DIR / "agent_state.json")
    if agent_state:
        interval = agent_state.get("interval_seconds")
        policy_count = len(agent_state.get("policy_rules", []))
        if interval:
            print(f"  Server interval: {interval}s")
        if policy_count:
            print(f"  Server policies: {policy_count} rules")

    # Config file
    print()
    cfg_path = _find_config_path()
    if cfg_path:
        print(f"  Config file    : {cfg_path}")
    else:
        print("  Config file    : not found")

    # Data directory
    print(f"  Data directory : {_STATE_DIR}")


# ── detec policy ─────────────────────────────────────────────────────


def cmd_policy_list(args: argparse.Namespace) -> None:
    """List all active policy rules."""
    from config_loader import load_policy_rules_from_file

    # Local file rules
    rules = load_policy_rules_from_file()

    # Server-pushed rules (overlay)
    agent_state = _read_json(_STATE_DIR / "agent_state.json")
    server_rules = (agent_state or {}).get("policy_rules", [])

    if not rules and not server_rules:
        print("No policy rules found.")
        print("  Local:  collector/config/policies.json (not found or empty)")
        print("  Server: no server-pushed rules")
        return

    if rules:
        print(f"Local policy rules ({len(rules)}):")
        print()
        _print_rules_table(rules)

    if server_rules:
        if rules:
            print()
        print(f"Server-pushed rules ({len(server_rules)}):")
        print()
        _print_rules_table(server_rules)


def _print_rules_table(rules: list[dict[str, Any]]) -> None:
    print(
        f"  {'RULE ID':<20} {'CATEGORY':<15} {'DECISION':<20} {'ACTIVE':<8} {'PREC':<5}"
    )
    print(f"  {'─' * 20} {'─' * 15} {'─' * 20} {'─' * 8} {'─' * 5}")
    for r in sorted(rules, key=lambda x: x.get("precedence", 999)):
        rule_id = r.get("rule_id", "?")
        category = r.get("category", "?")
        decision = r.get("decision_state", "?")
        active = "yes" if r.get("is_active", True) else "no"
        precedence = r.get("precedence", "?")
        print(
            f"  {rule_id:<20} {category:<15} {decision:<20} {active:<8} {precedence:<5}"
        )


def cmd_policy_show(args: argparse.Namespace) -> None:
    """Show a single policy rule by ID."""
    from config_loader import load_policy_rules_from_file

    target = args.rule_id.upper()
    rules = load_policy_rules_from_file()

    agent_state = _read_json(_STATE_DIR / "agent_state.json")
    server_rules = (agent_state or {}).get("policy_rules", [])

    all_rules = rules + server_rules
    match = [r for r in all_rules if r.get("rule_id", "").upper() == target]

    if not match:
        print(f"Rule '{target}' not found.")
        sys.exit(1)

    print(json.dumps(match[0], indent=2))


# ── detec detections ─────────────────────────────────────────────────


def cmd_detections(args: argparse.Namespace) -> None:
    """Show recent detection history from persisted state."""
    state_data = _read_json(_STATE_DIR / "state.json")
    if not state_data:
        print("No detection state found. Run 'detec scan' first.")
        return

    tools = state_data.get("tools", {})
    if not tools:
        print("No tools detected in state file.")
        return

    active = {k: v for k, v in tools.items() if v.get("detected", False)}
    cleared = {k: v for k, v in tools.items() if not v.get("detected", False)}

    if active:
        print(f"Active detections ({len(active)}):")
        print()
        print(f"  {'TOOL':<24} {'CLASS':<7} {'CONFIDENCE':<12} {'DECISION':<20}")
        print(f"  {'─' * 24} {'─' * 7} {'─' * 12} {'─' * 20}")
        for name, info in sorted(active.items()):
            cls = info.get("tool_class", "?")
            conf = info.get("confidence", 0)
            band = info.get("confidence_band", "?")
            decision = info.get("decision_state", "detect")
            print(f"  {name:<24} {cls:<7} {conf:.0%} ({band:<6}) {decision:<20}")
    else:
        print("No active detections.")

    if cleared:
        print()
        print(f"Previously detected, now cleared ({len(cleared)}):")
        for name in sorted(cleared):
            print(f"  {name}")


# ── detec posture ────────────────────────────────────────────────────


def cmd_posture_show(args: argparse.Namespace) -> None:
    """Show current enforcement posture."""
    posture_data = _read_json(_STATE_DIR / "posture.json")
    if not posture_data:
        print("Posture: passive (default, no state file)")
        print("Set with: detec posture set <passive|audit|active>")
        return

    posture = posture_data.get("posture", "passive")
    source = posture_data.get("source", "unknown")
    threshold = posture_data.get("auto_enforce_threshold", 0.75)
    allow_list = posture_data.get("allow_list", [])
    synced = posture_data.get("allow_list_synced_at")

    print(f"  Posture             : {posture}")
    print(f"  Source              : {source}")
    print(f"  Auto-enforce above  : {threshold:.0%} confidence")
    print(f"  Allow-list entries  : {len(allow_list)}")
    if allow_list:
        for pattern in sorted(allow_list):
            print(f"    - {pattern}")
    if synced:
        print(f"  Allow-list synced   : {_relative_time(synced)}")


def cmd_posture_set(args: argparse.Namespace) -> None:
    """Set enforcement posture (persists to disk)."""
    from enforcement.posture import PostureManager, VALID_POSTURES

    target = args.posture.lower()
    if target not in VALID_POSTURES:
        print(
            f"Invalid posture '{target}'. Must be one of: {', '.join(sorted(VALID_POSTURES))}"
        )
        sys.exit(1)

    mgr = PostureManager()
    old = mgr.posture
    mgr.update(target, source="cli")
    print(f"Posture changed: {old} -> {target}")
    if target == "active":
        print("Warning: active posture enables enforcement actions (kill, block).")


# ── detec config ─────────────────────────────────────────────────────


def cmd_config_show(args: argparse.Namespace) -> None:
    """Show fully resolved configuration from all sources."""
    from config_loader import load_collector_config

    cfg = load_collector_config()

    # Mask secrets
    secret_keys = {"api_key"}
    print("Resolved configuration (CLI > env > server state > config file > defaults):")
    print()
    for key in sorted(cfg):
        val = cfg[key]
        if key in secret_keys and isinstance(val, str) and val:
            val = _mask_secret(val)
        # Skip complex nested objects for readability
        if isinstance(val, (dict, list)):
            if isinstance(val, list) and len(val) == 0:
                val = "[]"
            elif isinstance(val, dict) and len(val) == 0:
                val = "{}"
            else:
                val = json.dumps(val, indent=2)
                if "\n" in val:
                    print(f"  {key}:")
                    for line in val.split("\n"):
                        print(f"    {line}")
                    continue
        print(f"  {key:<35} = {val}")


# ── detec doctor ─────────────────────────────────────────────────────


def cmd_doctor(args: argparse.Namespace) -> None:
    """Run health diagnostics."""
    issues: list[str] = []
    ok: list[str] = []

    print("Detec Agent Health Check")
    print("=" * 40)
    print()

    # 1. Python version
    v = sys.version_info
    print(f"  Python         : {v.major}.{v.minor}.{v.micro}")
    if v.minor < 11:
        issues.append(f"Python {v.major}.{v.minor} detected; 3.11+ recommended")

    # 2. Agent version
    try:
        from _version import __version__

        print(f"  Agent version  : {__version__}")
        ok.append("Agent version resolved")
    except ImportError:
        issues.append("Cannot import _version module")

    # 3. OS
    print(f"  Platform       : {sys.platform}")

    # 4. Telemetry provider
    try:
        from providers.registry import get_best_provider

        provider = get_best_provider("auto")
        print(f"  Telemetry      : {provider.name}")
        if provider.name == "Polling":
            issues.append(
                "Using psutil polling (reduced signal fidelity). "
                "Native telemetry (ESF/ETW) not available."
            )
        else:
            ok.append(f"Native telemetry available ({provider.name})")
    except Exception as e:
        issues.append(f"Telemetry provider check failed: {e}")

    # 5. Config file
    cfg_path = _find_config_path()
    if cfg_path:
        print(f"  Config file    : {cfg_path}")
        ok.append("Config file found")
    else:
        print("  Config file    : not found")
        issues.append("No config file found (collector.json or agent.env)")

    # 6. State directory
    if _STATE_DIR.is_dir():
        print(f"  State dir      : {_STATE_DIR}")
        ok.append("State directory exists")
    else:
        print(f"  State dir      : {_STATE_DIR} (missing)")
        issues.append("State directory does not exist")

    # 7. PID file staleness
    pid_file = _STATE_DIR / "agent.pid"
    if pid_file.is_file():
        try:
            pid = int(pid_file.read_text().strip())
            if _pid_alive(pid):
                ok.append(f"Daemon running (PID {pid})")
            else:
                issues.append(f"Stale PID file ({pid} not running). Remove: {pid_file}")
        except ValueError:
            issues.append(f"Corrupt PID file: {pid_file}")

    # 8. Policy file
    from config_loader import CONFIG_DIR

    policy_path = CONFIG_DIR / "policies.json"
    if policy_path.is_file():
        try:
            data = json.loads(policy_path.read_text(encoding="utf-8"))
            rule_count = len(data.get("rules", [])) + len(data.get("overlay_rules", []))
            print(f"  Policy file    : {policy_path} ({rule_count} rules)")
            ok.append(f"Policy file valid ({rule_count} rules)")
        except (json.JSONDecodeError, OSError) as e:
            issues.append(f"Policy file is invalid: {e}")
    else:
        issues.append(f"No policy file at {policy_path}")

    # 9. API connectivity (optional)
    from config_loader import load_collector_config

    cfg = load_collector_config()
    api_url = cfg.get("api_url", "")
    api_key = cfg.get("api_key", "")
    if api_url and api_key:
        import urllib.request
        import urllib.error

        try:
            req = urllib.request.Request(
                f"{api_url.rstrip('/')}/health",
                headers={"X-API-Key": api_key},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    print(f"  API connection : {api_url} (reachable)")
                    ok.append("API server reachable")
                else:
                    issues.append(f"API returned HTTP {resp.status}")
        except urllib.error.URLError as e:
            issues.append(f"API unreachable: {e.reason}")
        except Exception as e:
            issues.append(f"API check failed: {e}")
    else:
        print("  API connection : not configured (standalone mode)")

    # 10. Orphaned enforcement rules
    enforcement_path = _STATE_DIR / "enforcement_rules.json"
    if enforcement_path.is_file():
        try:
            rules = json.loads(enforcement_path.read_text(encoding="utf-8"))
            if rules:
                count = (
                    len(rules)
                    if isinstance(rules, list)
                    else len(rules.get("rules", []))
                )
                issues.append(f"Orphaned enforcement rules on disk ({count} rules)")
        except (json.JSONDecodeError, OSError):
            pass

    # Summary
    print()
    if not issues:
        print(f"  All checks passed ({len(ok)} ok)")
    else:
        print(f"  {len(ok)} ok, {len(issues)} issue(s):")
        for issue in issues:
            print(f"    ! {issue}")
