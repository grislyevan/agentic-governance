"""Windows Service wrapper for the Detec collector agent.

Uses pywin32's ``win32serviceutil.ServiceFramework`` to run the collector
daemon as a long-lived Windows Service. The service is registered as
"DetecAgent" with display name "Detec Agent".

This module is only imported on Windows.

Usage (from an elevated command prompt):
    detec-agent install     # register the service
    detec-agent start       # start it
    detec-agent stop        # stop it
    detec-agent remove      # unregister
"""

from __future__ import annotations

import os
import sys
import logging
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger("detec.agent.service")

try:
    import servicemanager  # type: ignore[import-untyped]
    import win32event  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]
    import win32serviceutil  # type: ignore[import-untyped]
    import pywintypes  # type: ignore[import-untyped]
except ImportError:
    raise SystemExit(
        "pywin32 is required for Windows Service support.\n"
        "Install with: pip install pywin32"
    )

def _find_python_service_exe() -> str:
    """Locate pythonservice.exe from the pywin32 installation.

    pywin32 ships pythonservice.exe as the proper SCM host process.
    Using python.exe directly as _exe_name_ causes error 1063 because
    python.exe does not call StartServiceCtrlDispatcher fast enough for SCM.
    """
    import site
    search_paths = []
    try:
        search_paths.extend(site.getsitepackages())
    except AttributeError:
        pass
    try:
        search_paths.append(site.getusersitepackages())
    except AttributeError:
        pass
    for sp in search_paths:
        candidate = Path(sp) / "win32" / "pythonservice.exe"
        if candidate.exists():
            return str(candidate)
    # Last resort fallback — service will likely still fail but with a clearer error
    logger.warning(
        "pythonservice.exe not found in site-packages; falling back to python.exe. "
        "Service start may fail with error 1063."
    )
    return sys.executable


# Failure recovery: restart after 60 s on first, second, and subsequent failures.
# ResetPeriod: seconds after which failure count resets (1 day).
_RESTART_DELAY_MS = 60_000
_RESET_PERIOD_SEC = 86400


def set_service_failure_recovery(service_name: str = "DetecAgent") -> None:
    """Configure Windows SCM failure actions for the service.

    Uses ``sc.exe failure`` for broad compatibility across pywin32 versions.
    """
    cmd = [
        "sc.exe",
        "failure",
        service_name,
        f"reset={_RESET_PERIOD_SEC}",
        f"actions=restart/{_RESTART_DELAY_MS}/restart/{_RESTART_DELAY_MS}/restart/{_RESTART_DELAY_MS}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        raise RuntimeError(
            f"Failed to set service failure recovery for {service_name}: "
            f"{err or out or f'exit code {result.returncode}'}"
        )


def _data_dir() -> Path:
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec" / "Agent"


def _load_env() -> None:
    env_file = _data_dir() / "agent.env"
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


class DetecAgentService(win32serviceutil.ServiceFramework):
    """Detec Agent as a Windows Service."""

    _svc_name_ = "DetecAgent"
    _svc_display_name_ = "Detec Agent"
    _svc_description_ = (
        "Agentic AI endpoint telemetry collector. "
        "Scans for AI tools and reports to the Detec central server."
    )
    _exe_name_ = _find_python_service_exe()
    _svc_deps_ = None
    _svc_start_type_ = win32service.SERVICE_AUTO_START

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._thread: threading.Thread | None = None

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        servicemanager.LogInfoMsg("Detec Agent stopping")

    def SvcDoRun(self) -> None:
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        try:
            self._run_agent()
        except Exception:
            logger.exception("Detec Agent crashed")
            servicemanager.LogErrorMsg("Detec Agent crashed unexpectedly")
        finally:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, ""),
            )

    def _run_agent(self) -> None:
        # Auto-configure from MSI trailer if agent.env doesn't exist yet
        try:
            from agent_cli import _try_extract_installer_config
            _try_extract_installer_config()
        except Exception:
            pass
        _load_env()

        # Ensure site-packages are importable when running as a Windows Service
        import site

        for sp in site.getsitepackages():
            if sp not in sys.path:
                sys.path.insert(0, sp)
        user_sp = site.getusersitepackages()
        if user_sp not in sys.path:
            sys.path.insert(0, user_sp)

        api_url = os.environ.get("AGENTIC_GOV_API_URL", "")
        api_key = os.environ.get("AGENTIC_GOV_API_KEY", "")
        interval = int(os.environ.get("AGENTIC_GOV_INTERVAL", "300"))

        if not api_url or not api_key:
            servicemanager.LogErrorMsg(
                "Detec Agent: AGENTIC_GOV_API_URL and AGENTIC_GOV_API_KEY must be set. "
                "Run 'detec-agent setup' first."
            )
            return

        # Tell SCM we're starting (up to 120s allowed for init)
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING, waitHint=120_000)

        # Import the daemon after reporting START_PENDING; log and exit if import fails.
        try:
            from main import _run_daemon
        except Exception as exc:
            servicemanager.LogErrorMsg(f"Detec Agent: failed to import _run_daemon: {exc}")
            return

        class ServiceArgs:
            """Mimics argparse.Namespace for _run_daemon."""
            pass

        args = ServiceArgs()
        args.api_url = api_url
        args.api_key = api_key
        args.interval = interval
        args.endpoint_id = None
        args.report_all = False
        args.verbose = False
        args.dry_run = False
        args.enforce = False
        args.sensitivity = "Tier0"
        args.actor_id = None
        args.output = "ndjson"

        try:
            self._thread = threading.Thread(target=_run_daemon, args=(args,), daemon=True)
            self._thread.start()
        except Exception as exc:
            servicemanager.LogErrorMsg(f"Detec Agent: failed to start daemon thread: {exc}")
            return

        # Signal SCM: we're running
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogInfoMsg(
            f"Detec Agent running (interval={interval}s, api={api_url})"
        )

        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

        self._thread.join(timeout=15)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # SCM started us with no args — must call dispatcher immediately
        # on the main thread with minimal delay.
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DetecAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    elif len(sys.argv) >= 2 and sys.argv[1] in ("install", "update", "remove", "start", "stop", "restart", "debug"):
        win32serviceutil.HandleCommandLine(DetecAgentService)
    else:
        win32serviceutil.HandleCommandLine(DetecAgentService)
