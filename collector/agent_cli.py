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
# Auto-config from MSI trailer (DETEC_CFG_V1)
# -------------------------------------------------------------------

_CFG_MAGIC = b"DETEC_CFG_V1\x00"


def _try_extract_installer_config() -> None:
    """Check if agent.env exists; if not, look for a DETEC_CFG_V1 config
    trailer appended to the MSI that installed us and write agent.env from it.

    This enables zero-touch config: the server stamps the MSI with tenant
    config at download time, and the agent self-configures on first start.
    """
    import json
    import struct

    env = _env_path()
    if env.exists():
        return  # already configured

    # Find the MSI: check Windows Installer registry for our product
    # or look for the MSI next to our exe (dev/manual installs)
    msi_path = _find_source_msi()
    if not msi_path or not os.path.exists(msi_path):
        return

    try:
        with open(msi_path, "rb") as f:
            data = f.read()

        # Trailer format: [MAGIC] [JSON] [4-byte LE len] [MAGIC]
        if not data.endswith(_CFG_MAGIC):
            return

        # Strip trailing magic
        data = data[: -len(_CFG_MAGIC)]

        # Read 4-byte length
        if len(data) < 4:
            return
        json_len = struct.unpack("<I", data[-4:])[0]
        data = data[:-4]

        # Read JSON
        if len(data) < json_len + len(_CFG_MAGIC):
            return
        json_bytes = data[-json_len:]

        # Verify leading magic
        prefix = data[-(json_len + len(_CFG_MAGIC)) : -json_len]
        if prefix != _CFG_MAGIC:
            return

        config = json.loads(json_bytes)
        api_url = config.get("api_url", "")
        api_key = config.get("api_key", "")
        tenant_id = config.get("tenant_id", "")

        if not api_url or not api_key:
            return

        _ensure_data_dir()

        from urllib.parse import urlparse
        gh = urlparse(api_url).hostname or "localhost"

        lines = [
            f"AGENTIC_GOV_API_URL={api_url}",
            f"AGENTIC_GOV_API_KEY={api_key}",
            f"AGENTIC_GOV_TENANT_ID={tenant_id}",
            "AGENTIC_GOV_PROTOCOL=auto",
            f"AGENTIC_GOV_GATEWAY_HOST={gh}",
            "AGENTIC_GOV_GATEWAY_PORT=8001",
            "AGENTIC_GOV_INTERVAL=300",
        ]
        env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Auto-configured from installer trailer: %s", env)

    except Exception:
        logger.debug("No installer config trailer found", exc_info=True)


def _find_source_msi() -> str | None:
    """Try to locate the MSI that installed this agent."""
    if not _IS_WINDOWS:
        return None

    # Method 1: Check common download locations for all user profiles
    search_dirs = [
        Path(r"C:\Detec"),
        Path(r"C:\temp"),
    ]
    # Check all user Downloads folders (SYSTEM can read them)
    users_dir = Path(r"C:\Users")
    if users_dir.exists():
        for user_dir in users_dir.iterdir():
            dl = user_dir / "Downloads"
            if dl.is_dir():
                search_dirs.append(dl)

    for candidate in search_dirs:
        try:
            for msi in candidate.glob("DetecAgent*.msi"):
                return str(msi)
        except (OSError, PermissionError):
            continue

    # Method 2: Check Windows Installer cache via registry
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        for i in range(winreg.QueryInfoKey(key)[0]):
            subkey_name = winreg.EnumKey(key, i)
            try:
                subkey = winreg.OpenKey(key, subkey_name)
                name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                if "Detec Agent" in str(name):
                    source, _ = winreg.QueryValueEx(subkey, "InstallSource")
                    source_msi = Path(source) / "DetecAgent.msi"
                    if source_msi.exists():
                        return str(source_msi)
            except (OSError, FileNotFoundError):
                continue
    except Exception:
        pass

    return None


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

    protocol = getattr(args, "protocol", "auto")
    gateway_port = getattr(args, "gateway_port", 8001)
    from urllib.parse import urlparse

    gh = urlparse(args.api_url).hostname or "localhost"

    lines = [
        f"AGENTIC_GOV_API_URL={args.api_url}",
        f"AGENTIC_GOV_API_KEY={args.api_key}",
        f"AGENTIC_GOV_INTERVAL={args.interval}",
        f"AGENTIC_GOV_PROTOCOL={protocol}",
        f"AGENTIC_GOV_GATEWAY_HOST={gh}",
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
    cfg["session_report"] = getattr(args, "session_report", False)

    sys.exit(run_scan(argparse.Namespace(**cfg)))


def cmd_session_report(args: argparse.Namespace) -> None:
    """Run a scan and print agent session report(s) for detected tools."""
    from config_loader import load_collector_config
    from main import run_scan

    cfg = load_collector_config()
    cfg["dry_run"] = True
    cfg["verbose"] = args.verbose
    cfg["interval"] = 0
    cfg["report_all"] = True
    cfg["enforce"] = False
    cfg["session_report"] = True

    sys.exit(run_scan(argparse.Namespace(**cfg)))


# -------------------------------------------------------------------
# ``detec-agent run`` (foreground daemon)
# -------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run the agent daemon in the foreground."""
    _try_extract_installer_config()
    _load_env()

    from config_loader import load_collector_config
    from main import _run_daemon

    cfg = load_collector_config()

    if args.api_url:
        cfg["api_url"] = args.api_url
    if args.api_key:
        cfg["api_key"] = args.api_key
    cfg["interval"] = args.interval
    cfg["protocol"] = getattr(args, "protocol", cfg.get("protocol", "auto"))
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
# Scheduled Task commands (replaces Windows Service for PyInstaller)
# -------------------------------------------------------------------

_TASK_NAME = "DetecAgent"


def cmd_write_env(args: argparse.Namespace) -> None:
    """Write agent.env from CLI args or MSI trailer. Called by MSI custom action."""
    import json
    import struct

    api_url = getattr(args, "api_url", None) or ""
    api_key = getattr(args, "api_key", None) or ""
    tenant_id = getattr(args, "tenant_id", None) or ""
    msi_path = getattr(args, "from_msi", None) or ""

    # If --from-msi is provided, extract config from the MSI trailer
    if msi_path and os.path.exists(msi_path):
        try:
            with open(msi_path, "rb") as f:
                data = f.read()
            if data.endswith(_CFG_MAGIC):
                data = data[: -len(_CFG_MAGIC)]
                json_len = struct.unpack("<I", data[-4:])[0]
                data = data[:-4]
                json_bytes = data[-json_len:]
                config = json.loads(json_bytes)
                api_url = config.get("api_url", api_url)
                api_key = config.get("api_key", api_key)
                tenant_id = config.get("tenant_id", tenant_id)
                print(f"Extracted config from MSI trailer: {msi_path}")
        except Exception as e:
            print(f"Warning: failed to read MSI trailer: {e}", file=sys.stderr)

    # Skip if values are still placeholders
    if not api_url or api_url == "PLACEHOLDER" or not api_key or api_key == "PLACEHOLDER":
        print("No valid config found (PLACEHOLDER or empty). Skipping write-env.", file=sys.stderr)
        print("The agent will self-configure from the MSI trailer on first start.", file=sys.stderr)
        return

    _ensure_data_dir()
    env_file = _env_path()

    from urllib.parse import urlparse
    gh = urlparse(api_url).hostname or "localhost"

    lines = [
        f"AGENTIC_GOV_API_URL={api_url}",
        f"AGENTIC_GOV_API_KEY={api_key}",
        f"AGENTIC_GOV_TENANT_ID={tenant_id}",
        "AGENTIC_GOV_PROTOCOL=auto",
        f"AGENTIC_GOV_GATEWAY_HOST={gh}",
        "AGENTIC_GOV_GATEWAY_PORT=8001",
        "AGENTIC_GOV_INTERVAL=300",
    ]
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Config written to {env_file}")


def cmd_install_task(args: argparse.Namespace) -> None:
    """Register a Scheduled Task to run the agent at system startup."""
    if not _IS_WINDOWS:
        print("Scheduled Task install is only supported on Windows.")
        sys.exit(1)

    import subprocess

    exe = sys.executable
    if getattr(sys, "frozen", False):
        exe = sys.executable  # the frozen .exe itself

    # Create the task: runs at startup, under SYSTEM, restarts on failure
    result = subprocess.run(
        [
            "schtasks.exe", "/create",
            "/tn", _TASK_NAME,
            "/tr", f'"{exe}" run',
            "/sc", "onstart",
            "/ru", "SYSTEM",
            "/rl", "HIGHEST",
            "/f",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Failed to create scheduled task: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"Scheduled task '{_TASK_NAME}' registered.")

    # Start it immediately
    result = subprocess.run(
        ["schtasks.exe", "/run", "/tn", _TASK_NAME],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{_TASK_NAME}' started.")
    else:
        print(f"Task registered but failed to start: {result.stderr.strip()}", file=sys.stderr)


def cmd_remove_task(args: argparse.Namespace) -> None:
    """Stop and unregister the Scheduled Task."""
    if not _IS_WINDOWS:
        print("Scheduled Task remove is only supported on Windows.")
        sys.exit(1)

    import subprocess

    # Stop first (ignore errors if not running)
    subprocess.run(
        ["schtasks.exe", "/end", "/tn", _TASK_NAME],
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        ["schtasks.exe", "/delete", "/tn", _TASK_NAME, "/f"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{_TASK_NAME}' removed.")
    else:
        print(f"Failed to remove task: {result.stderr.strip()}", file=sys.stderr)


# -------------------------------------------------------------------
# ``detec-agent watchdog``
# -------------------------------------------------------------------

def cmd_watchdog(args: argparse.Namespace) -> None:
    """Run the watchdog process — monitors the agent and restarts it if it dies."""
    from watchdog import run_watchdog
    run_watchdog()


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
        import subprocess
        result = subprocess.run(
            ["schtasks.exe", "/query", "/tn", _TASK_NAME, "/fo", "list"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if line.strip().startswith("Status:"):
                    print(f"Scheduled Task : {line.split(':', 1)[1].strip()}")
                    break
        else:
            print("Scheduled Task : not registered")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _load_env() -> None:
    env_file = _env_path()
    if not env_file.exists():
        return
    # utf-8-sig strips BOM if present (PowerShell Out-File adds one)
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
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
    p_setup.add_argument(
        "--protocol",
        choices=["auto", "http", "tcp"],
        default="auto",
        help="Transport: auto (TCP first, HTTP fallback), tcp, or http (default: auto)",
    )
    p_setup.add_argument("--gateway-port", dest="gateway_port", type=int, default=8001, help="Gateway port for TCP protocol (default: 8001)")
    p_setup.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_setup.set_defaults(func=cmd_setup)

    # --- scan ---
    p_scan = sub.add_parser("scan", help="Run a one-shot scan and print results")
    p_scan.add_argument("--verbose", action="store_true", help="Show detailed scan output")
    p_scan.add_argument("--session-report", action="store_true", dest="session_report", help="Also print agent session report(s)")
    p_scan.set_defaults(func=cmd_scan)

    # --- session-report ---
    p_session_report = sub.add_parser("session-report", help="Run scan and print agent session report (tool, duration, actions, risk signals)")
    p_session_report.add_argument("--verbose", action="store_true", help="Show detailed scan output")
    p_session_report.set_defaults(func=cmd_session_report)

    # --- run ---
    p_run = sub.add_parser("run", help="Run the agent daemon in the foreground")
    p_run.add_argument("--api-url", help="Central server API URL")
    p_run.add_argument("--api-key", help="API key for authentication")
    p_run.add_argument("--interval", type=int, default=300, help="Scan interval in seconds (default: 300)")
    p_run.add_argument(
        "--protocol",
        choices=["auto", "http", "tcp"],
        default="auto",
        help="Transport: auto, tcp, or http (default: auto)",
    )
    p_run.add_argument("--report-all", action="store_true", default=False, help="Report all detections every cycle (default: changes only)")
    p_run.add_argument("--enforce", action="store_true", default=False, help="Execute enforcement actions for block decisions")
    p_run.add_argument("--verbose", action="store_true", help="Show detailed scan output")
    p_run.set_defaults(func=cmd_run)

    # --- Scheduled Task commands (Windows) ---
    p_install_task = sub.add_parser("install-task", help="Register a Scheduled Task to run the agent at startup (Windows)")
    p_install_task.set_defaults(func=cmd_install_task)

    p_remove_task = sub.add_parser("remove-task", help="Stop and unregister the Scheduled Task (Windows)")
    p_remove_task.set_defaults(func=cmd_remove_task)

    # --- write-env (used by MSI custom action) ---
    p_write_env = sub.add_parser("write-env", help="Write agent.env config file (used by MSI installer)")
    p_write_env.add_argument("--api-url", default="", help="Server API URL")
    p_write_env.add_argument("--api-key", default="", help="API key")
    p_write_env.add_argument("--tenant-id", default="", help="Tenant ID")
    p_write_env.add_argument("--from-msi", default="", help="Path to MSI to extract config trailer from")
    p_write_env.set_defaults(func=cmd_write_env)

    # --- Legacy Windows Service commands (kept for backward compat) ---
    p_install = sub.add_parser("install", help="Install as a Windows Service (legacy)")
    p_install.set_defaults(func=cmd_install)

    p_remove = sub.add_parser("remove", help="Remove the Windows Service (legacy)")
    p_remove.set_defaults(func=cmd_remove)

    p_start = sub.add_parser("start", help="Start the Windows Service (legacy)")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop the Windows Service (legacy)")
    p_stop.set_defaults(func=cmd_stop)

    # --- status ---
    p_status = sub.add_parser("status", help="Show agent status and config")
    p_status.set_defaults(func=cmd_status)

    # --- watchdog ---
    p_watchdog = sub.add_parser(
        "watchdog",
        help="Run the watchdog process that monitors and restarts the agent (Windows)",
    )
    p_watchdog.set_defaults(func=cmd_watchdog)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


def _start_daemon_headless() -> None:
    """Called when the frozen exe runs with no arguments (e.g. via Scheduled Task).

    Loads agent.env, builds a config namespace, and enters the daemon loop.
    The pywin32 Windows Service approach (pythonservice.exe) doesn't work with
    PyInstaller bundles, so Scheduled Task is the supported deployment model.
    """
    _try_extract_installer_config()
    _load_env()

    from config_loader import load_collector_config
    from main import _run_daemon

    cfg = load_collector_config()
    ns = argparse.Namespace(**cfg)

    if not ns.api_url or not ns.api_key:
        logger.error(
            "api_url and api_key are required. "
            "Run 'detec-agent setup' first, or ensure agent.env exists at %s",
            _env_path(),
        )
        sys.exit(1)
    if ns.interval <= 0:
        ns.interval = 300

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    _run_daemon(ns)


if __name__ == "__main__":
    if (
        _IS_WINDOWS
        and getattr(sys, "frozen", False)
        and len(sys.argv) == 1
    ):
        _start_daemon_headless()
    else:
        main()
