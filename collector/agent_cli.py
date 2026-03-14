"""Detec Agent CLI.

Entry point for running the collector agent in various modes:
  - One-shot scan: ``detec-agent scan``
  - Daemon (foreground): ``detec-agent run``
  - Windows Service management: ``detec-agent install|start|stop|remove|set-recovery|install-service``
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
    from config_loader import load_collector_config
    from main import run_scan

    cfg = load_collector_config()
    cfg["dry_run"] = True
    cfg["verbose"] = args.verbose
    cfg["interval"] = 0
    cfg["report_all"] = True
    cfg["enforce"] = False

    sys.exit(run_scan(argparse.Namespace(**cfg)))


# -------------------------------------------------------------------
# ``detec-agent run`` (foreground daemon)
# -------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run the agent daemon in the foreground."""
    _load_env()

    from config_loader import load_collector_config
    from main import _run_daemon

    cfg = load_collector_config()

    if args.api_url:
        cfg["api_url"] = args.api_url
    if args.api_key:
        cfg["api_key"] = args.api_key
    cfg["interval"] = args.interval
    cfg["protocol"] = getattr(args, "protocol", cfg.get("protocol", "http"))
    cfg["verbose"] = args.verbose
    cfg["report_all"] = getattr(args, "report_all", cfg.get("report_all", False))
    cfg["enforce"] = getattr(args, "enforce", False)

    ns = argparse.Namespace(**cfg)

    if not ns.api_url or not ns.api_key:
        print(
            "Error: api_url and api_key are required. "
            "Run 'detec-agent setup' first, or pass --api-url and --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)
    if ns.interval <= 0:
        ns.interval = 300

    logging.basicConfig(
        level=logging.DEBUG if ns.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    _run_daemon(ns)


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


def cmd_set_recovery(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service set-recovery is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_agent_service import set_service_failure_recovery

    set_service_failure_recovery()
    print("Failure recovery configured: service will restart after 60 s on failure.")


def cmd_install_service(args: argparse.Namespace) -> None:
    """Install, start, and configure failure recovery for the Windows Service in one step."""
    if not _IS_WINDOWS:
        print("Service install-service is only supported on Windows.")
        sys.exit(1)

    import subprocess

    _load_env()
    _require_pywin32()

    exe = sys.executable
    cwd = os.getcwd()
    for step in ("install", "start", "set-recovery"):
        result = subprocess.run([exe, step], cwd=cwd)
        if result.returncode != 0:
            logger.error("install-service: %s failed with exit code %d", step, result.returncode)
            sys.exit(result.returncode)
    print("Service installed, started, and failure recovery configured.")


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

_LEGACY_FLAGS = {
    "--output", "--endpoint-id", "--actor-id", "--sensitivity",
    "--dry-run", "--verbose", "--interval", "--api-url", "--api-key",
    "--report-all", "--enforce", "--protocol", "--gateway-host",
    "--gateway-port",
}


def main() -> None:
    # Backward compatibility: if invoked with legacy flat flags (no
    # subcommand), delegate to the flat-flag parser in main.py so
    # existing LaunchAgents, systemd units, and scripts keep working.
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        if sys.argv[1].split("=")[0] in _LEGACY_FLAGS:
            from main import main as legacy_main
            legacy_main()
            return

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
    p_setup.add_argument("--protocol", choices=["http", "tcp"], default="http", help="Transport protocol (default: http)")
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
    p_run.add_argument("--protocol", choices=["http", "tcp"], default="http", help="Transport protocol (default: http)")
    p_run.add_argument("--report-all", action="store_true", default=False, help="Report all detections every cycle (default: changes only)")
    p_run.add_argument("--enforce", action="store_true", default=False, help="Execute enforcement actions for block decisions")
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

    p_set_recovery = sub.add_parser(
        "set-recovery",
        help="Configure restart-on-failure for the Windows Service (run after install)",
    )
    p_set_recovery.set_defaults(func=cmd_set_recovery)

    p_install_service = sub.add_parser(
        "install-service",
        help="Install, start, and set recovery for the Windows Service (one step)",
    )
    p_install_service.set_defaults(func=cmd_install_service)

    # --- status ---
    p_status = sub.add_parser("status", help="Show agent status and config")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


def _start_as_windows_service() -> None:
    """Called when the SCM starts us with no arguments (frozen exe only)."""
    import servicemanager  # type: ignore[import-untyped]
    from win_agent_service import DetecAgentService

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(DetecAgentService)
    servicemanager.StartServiceCtrlDispatcher()


if __name__ == "__main__":
    if (
        _IS_WINDOWS
        and getattr(sys, "frozen", False)
        and len(sys.argv) == 1
    ):
        _start_as_windows_service()
    else:
        main()
