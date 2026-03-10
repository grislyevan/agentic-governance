"""Detec Agent CLI.

Entry point for running the collector agent in various modes:
  - One-shot scan: ``detec-agent scan``
  - Daemon (foreground): ``detec-agent run``
  - Windows Service management: ``detec-agent install|start|stop|remove``
  - Configuration: ``detec-agent setup``
  - Status check: ``detec-agent status``

When frozen by PyInstaller, this module is the console script.
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

logger = logging.getLogger("detec.agent")

_IS_WINDOWS = sys.platform == "win32"

_collector_dir = Path(__file__).resolve().parent
if str(_collector_dir) not in sys.path:
    sys.path.insert(0, str(_collector_dir))


def _data_dir() -> Path:
    if _IS_WINDOWS:
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec" / "Agent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Detec"
    return Path.home() / ".local" / "share" / "detec"


def _ensure_data_dir() -> Path:
    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _env_path() -> Path:
    return _data_dir() / "agent.env"


# -------------------------------------------------------------------
# ``detec-agent setup``
# -------------------------------------------------------------------

def cmd_setup(args: argparse.Namespace) -> None:
    """Write an agent.env config file with API URL and key."""
    env_file = _env_path()
    _ensure_data_dir()

    if env_file.exists() and not args.force:
        print(f"Config already exists at {env_file}")
        print("Use --force to overwrite.")
        return

    protocol = getattr(args, "protocol", "http")
    gateway_port = getattr(args, "gateway_port", 8001)

    lines = [
        f"AGENTIC_GOV_API_URL={args.api_url}",
        f"AGENTIC_GOV_API_KEY={args.api_key}",
        f"AGENTIC_GOV_INTERVAL={args.interval}",
        f"AGENTIC_GOV_PROTOCOL={protocol}",
        f"AGENTIC_GOV_GATEWAY_PORT={gateway_port}",
        "",
    ]
    env_file.write_text("\n".join(lines), encoding="utf-8")

    print(f"Config written to {env_file}")
    print()
    print(f"  API URL:       {args.api_url}")
    print(f"  Protocol:      {protocol}")
    print(f"  Gateway port:  {gateway_port}")
    print(f"  Interval:      {args.interval}s")
    print()
    print("Next steps:")
    if _IS_WINDOWS:
        print("  detec-agent install   (register as a Windows Service)")
        print("  detec-agent start     (start the service)")
    else:
        print("  detec-agent run       (start the agent)")


# -------------------------------------------------------------------
# ``detec-agent scan`` (one-shot)
# -------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> None:
    """Run a single scan and print results."""
    from main import run_scan

    class ScanArgs:
        dry_run = True
        verbose = args.verbose
        interval = 0
        output = "ndjson"
        endpoint_id = None
        actor_id = None
        sensitivity = "Tier0"
        api_url = None
        api_key = None
        report_all = True
        enforce = False

    sys.exit(run_scan(ScanArgs()))


# -------------------------------------------------------------------
# ``detec-agent run`` (foreground daemon)
# -------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run the agent daemon in the foreground."""
    _load_env()

    from main import main as collector_main

    protocol = getattr(args, "protocol", "http")
    sys.argv = [
        "detec-agent",
        "--interval", str(args.interval),
        "--api-url", args.api_url,
        "--api-key", args.api_key,
        "--protocol", protocol,
    ]
    if args.verbose:
        sys.argv.append("--verbose")

    collector_main()


# -------------------------------------------------------------------
# Windows Service commands
# -------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service install is only supported on Windows.")
        print("Use 'detec-agent run' on macOS/Linux, or configure a LaunchAgent/systemd unit.")
        sys.exit(1)

    _load_env()
    _require_pywin32()

    from win_agent_service import DetecAgentService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-agent", "install"]
    win32serviceutil.HandleCommandLine(DetecAgentService)


def cmd_remove(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service remove is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_agent_service import DetecAgentService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-agent", "remove"]
    win32serviceutil.HandleCommandLine(DetecAgentService)


def cmd_start(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service start is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_agent_service import DetecAgentService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-agent", "start"]
    win32serviceutil.HandleCommandLine(DetecAgentService)


def cmd_stop(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service stop is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_agent_service import DetecAgentService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-agent", "stop"]
    win32serviceutil.HandleCommandLine(DetecAgentService)


# -------------------------------------------------------------------
# ``detec-agent status``
# -------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    env_file = _env_path()
    data_dir = _data_dir()

    print(f"Data directory : {data_dir}")
    print(f"Config file    : {env_file} ({'exists' if env_file.exists() else 'NOT FOUND'})")

    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, val = line.partition("=")
                if "KEY" in key.upper():
                    val = val[:8] + "..." if len(val) > 8 else val
                print(f"  {key.strip()} = {val.strip()}")

    if _IS_WINDOWS:
        try:
            import win32serviceutil  # type: ignore[import-untyped]
            status = win32serviceutil.QueryServiceStatus("DetecAgent")
            state_map = {1: "stopped", 2: "starting", 3: "stopping", 4: "running"}
            print(f"Service        : {state_map.get(status[1], f'unknown ({status[1]})')}")
        except Exception:
            print("Service        : not installed")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _load_env() -> None:
    env_file = _env_path()
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _require_pywin32() -> None:
    try:
        import win32serviceutil  # noqa: F401
    except ImportError:
        print("pywin32 is required for Windows Service support.")
        print("Install it with: pip install pywin32")
        sys.exit(1)


# -------------------------------------------------------------------
# Argument parser
# -------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="detec-agent",
        description="Detec Agent: endpoint telemetry collector for agentic AI tools",
    )
    sub = parser.add_subparsers(dest="command")

    # --- setup ---
    p_setup = sub.add_parser("setup", help="Configure the agent (API URL, key, interval)")
    p_setup.add_argument("--api-url", required=True, help="Central server API URL, e.g. http://server:8000/api")
    p_setup.add_argument("--api-key", required=True, help="API key for authentication")
    p_setup.add_argument("--interval", type=int, default=300, help="Scan interval in seconds (default: 300)")
    p_setup.add_argument("--protocol", choices=["http", "tcp"], default="tcp", help="Transport protocol (default: tcp)")
    p_setup.add_argument("--gateway-port", dest="gateway_port", type=int, default=8001, help="Gateway port for TCP protocol (default: 8001)")
    p_setup.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_setup.set_defaults(func=cmd_setup)

    # --- scan ---
    p_scan = sub.add_parser("scan", help="Run a one-shot scan and print results")
    p_scan.add_argument("--verbose", action="store_true", help="Show detailed scan output")
    p_scan.set_defaults(func=cmd_scan)

    # --- run ---
    p_run = sub.add_parser("run", help="Run the agent daemon in the foreground")
    p_run.add_argument("--api-url", help="Central server API URL")
    p_run.add_argument("--api-key", help="API key for authentication")
    p_run.add_argument("--interval", type=int, default=300, help="Scan interval in seconds (default: 300)")
    p_run.add_argument("--protocol", choices=["http", "tcp"], default="tcp", help="Transport protocol (default: tcp)")
    p_run.add_argument("--verbose", action="store_true", help="Show detailed scan output")
    p_run.set_defaults(func=cmd_run)

    # --- Windows service commands ---
    p_install = sub.add_parser("install", help="Install as a Windows Service")
    p_install.set_defaults(func=cmd_install)

    p_remove = sub.add_parser("remove", help="Remove the Windows Service")
    p_remove.set_defaults(func=cmd_remove)

    p_start = sub.add_parser("start", help="Start the Windows Service")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop the Windows Service")
    p_stop.set_defaults(func=cmd_stop)

    # --- status ---
    p_status = sub.add_parser("status", help="Show agent status and config")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
