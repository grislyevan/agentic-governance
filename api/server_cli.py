"""Detec Server CLI.

Entry point for running the Detec server in various modes:
  - Foreground (development): ``detec-server run``
  - Windows Service management: ``detec-server install|start|stop|remove``
  - First-run setup: ``detec-server setup``
  - Status check: ``detec-server status``

When frozen by PyInstaller, this module is the console script.
"""

from __future__ import annotations

import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

logger = logging.getLogger("detec.server")

_IS_WINDOWS = sys.platform == "win32"

# The api/ directory must be importable.
_api_dir = Path(__file__).resolve().parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))


def _data_dir() -> Path:
    """Platform-appropriate writable data directory."""
    if _IS_WINDOWS:
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Detec"
    return Path.home() / ".local" / "share" / "detec"


def _ensure_data_dir() -> Path:
    d = _data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _env_path() -> Path:
    return _data_dir() / "server.env"


# -------------------------------------------------------------------
# ``detec-server setup``
# -------------------------------------------------------------------

def cmd_setup(args: argparse.Namespace) -> None:
    """Generate secrets and write a server.env file for first-run."""
    env_file = _env_path()
    data_dir = _ensure_data_dir()

    if env_file.exists() and not args.force:
        print(f"Config already exists at {env_file}")
        print("Use --force to overwrite.")
        return

    jwt_secret = secrets.token_hex(32)
    seed_password = secrets.token_urlsafe(16)

    gateway_port = getattr(args, "gateway_port", 8001)

    lines = [
        f"JWT_SECRET={jwt_secret}",
        f"SEED_ADMIN_PASSWORD={seed_password}",
        f"SEED_ADMIN_EMAIL={args.admin_email}",
        f"GATEWAY_PORT={gateway_port}",
        "ENV=production",
        "",
    ]
    env_file.write_text("\n".join(lines), encoding="utf-8")

    print(f"Config written to {env_file}")
    print(f"Database will be stored in {data_dir}")
    print()
    print("  Seed admin email:    " + args.admin_email)
    print("  Seed admin password: " + seed_password)
    print()
    print("Save the password above. It will not be shown again.")
    print()
    print("Next steps:")
    if _IS_WINDOWS:
        print("  detec-server install   (register as a Windows Service)")
        print("  detec-server start     (start the service)")
    else:
        print("  detec-server run       (start the server)")


# -------------------------------------------------------------------
# ``detec-server run``
# -------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run the server in the foreground (development/Linux/macOS)."""
    _load_env()

    import uvicorn

    if args.reload:
        # reload requires the string form (only works in development)
        uvicorn.run(
            "main:app",
            host=args.host,
            port=args.port,
            log_level="info",
            reload=True,
        )
    else:
        from main import app
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            log_level="info",
        )


# -------------------------------------------------------------------
# ``detec-server install`` (Windows only)
# -------------------------------------------------------------------

def cmd_install(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service install is only supported on Windows.")
        print("Use 'detec-server run' on macOS/Linux, or create a systemd unit.")
        sys.exit(1)

    _load_env()
    _require_pywin32()

    from win_service import DetecService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-server", "install"]
    win32serviceutil.HandleCommandLine(DetecService)


def cmd_remove(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service remove is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_service import DetecService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-server", "remove"]
    win32serviceutil.HandleCommandLine(DetecService)


def cmd_start(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service start is only supported on Windows.")
        print("Use 'detec-server run' on macOS/Linux.")
        sys.exit(1)

    _require_pywin32()

    from win_service import DetecService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-server", "start"]
    win32serviceutil.HandleCommandLine(DetecService)


def cmd_stop(args: argparse.Namespace) -> None:
    if not _IS_WINDOWS:
        print("Service stop is only supported on Windows.")
        sys.exit(1)

    _require_pywin32()

    from win_service import DetecService
    import win32serviceutil  # type: ignore[import-untyped]

    sys.argv = ["detec-server", "stop"]
    win32serviceutil.HandleCommandLine(DetecService)


# -------------------------------------------------------------------
# ``detec-server status``
# -------------------------------------------------------------------

def cmd_status(args: argparse.Namespace) -> None:
    """Print server status (config location, DB path, service state)."""
    env_file = _env_path()
    data_dir = _data_dir()

    print(f"Data directory : {data_dir}")
    print(f"Config file    : {env_file} ({'exists' if env_file.exists() else 'NOT FOUND'})")

    db_path = data_dir / "detec.db"
    if db_path.exists():
        size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"Database       : {db_path} ({size_mb:.1f} MB)")
    else:
        print(f"Database       : {db_path} (not created yet)")

    if _IS_WINDOWS:
        try:
            import win32serviceutil  # type: ignore[import-untyped]
            status = win32serviceutil.QueryServiceStatus("DetecServer")
            state_map = {1: "stopped", 2: "starting", 3: "stopping", 4: "running"}
            print(f"Service        : {state_map.get(status[1], f'unknown ({status[1]})')}")
        except Exception:
            print("Service        : not installed")


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def _load_env() -> None:
    """Load server.env if it exists; don't overwrite already-set vars."""
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

def _enter_service_mode() -> None:
    """Called when the exe is started by the Windows SCM (no arguments).

    This is the entry path when the service starts on boot or via
    ``net start DetecServer``.  We must register with the SCM dispatcher
    immediately or Windows will report Error 1053.
    """
    import servicemanager  # type: ignore[import-untyped]
    from win_service import DetecService

    _load_env()
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(DetecService)
    servicemanager.StartServiceCtrlDispatcher()


def main() -> None:
    # When launched by the Windows SCM with no arguments, enter service mode
    # immediately instead of falling through to argparse.
    if _IS_WINDOWS and len(sys.argv) == 1:
        _enter_service_mode()
        return

    parser = argparse.ArgumentParser(
        prog="detec-server",
        description="Detec Server: endpoint telemetry and policy engine",
    )
    sub = parser.add_subparsers(dest="command")

    # --- setup ---
    p_setup = sub.add_parser("setup", help="First-run setup: generate secrets and config")
    p_setup.add_argument(
        "--admin-email", default="admin@example.com",
        help="Email for the seed admin user (default: admin@example.com)",
    )
    p_setup.add_argument("--gateway-port", dest="gateway_port", type=int, default=8001, help="Binary protocol gateway port (default: 8001)")
    p_setup.add_argument("--force", action="store_true", help="Overwrite existing config")
    p_setup.set_defaults(func=cmd_setup)

    # --- run ---
    p_run = sub.add_parser("run", help="Run the server in the foreground")
    p_run.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    p_run.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    p_run.add_argument("--reload", action="store_true", help="Enable auto-reload (dev only)")
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
    p_status = sub.add_parser("status", help="Show server status")
    p_status.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
