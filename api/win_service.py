"""Windows Service wrapper for the Detec server.

Uses pywin32's ``win32serviceutil.ServiceFramework`` to run the FastAPI
application under uvicorn as a long-lived Windows Service.  The service
is registered as "DetecServer" with display name "Detec Server".

This module is only imported on Windows; non-Windows platforms use
``detec-server run`` (foreground) or a systemd unit instead.

Usage (from an elevated command prompt):
    detec-server install     # register the service
    detec-server start       # start it
    detec-server stop        # stop it
    detec-server remove      # unregister

Or directly:
    python win_service.py install
"""

from __future__ import annotations

import os
import sys
import logging
import traceback
import threading
from pathlib import Path

logger = logging.getLogger("detec.service")

# In a PyInstaller onedir bundle, sys._MEIPASS points to the _internal
# directory containing all bundled modules and data files.  Use it as
# the canonical "api dir" so that os.chdir and sys.path are correct
# regardless of the CWD the SCM launches us from (usually system32).
_api_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

try:
    import servicemanager  # type: ignore[import-untyped]
    import win32event  # type: ignore[import-untyped]
    import win32service  # type: ignore[import-untyped]
    import win32serviceutil  # type: ignore[import-untyped]
except ImportError:
    raise SystemExit(
        "pywin32 is required for Windows Service support.\n"
        "Install with: pip install pywin32"
    )


def _data_dir() -> Path:
    return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec"


def _load_env() -> None:
    """Load server.env into os.environ (skip keys already set)."""
    env_file = _data_dir() / "server.env"
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


class DetecService(win32serviceutil.ServiceFramework):
    """Detec Server as a Windows Service."""

    _svc_name_ = "DetecServer"
    _svc_display_name_ = "Detec Server"
    _svc_description_ = (
        "Agentic AI endpoint telemetry and policy server. "
        "Provides the API and dashboard at http://localhost:8000."
    )
    _exe_name_ = sys.executable
    _exe_args_ = ""
    _svc_start_type_ = win32service.SERVICE_AUTO_START

    def __init__(self, args: list[str]) -> None:
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self._server: object | None = None
        self._thread: threading.Thread | None = None

    def SvcStop(self) -> None:
        """Called by the SCM to stop the service."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

        if self._server is not None:
            self._server.should_exit = True  # type: ignore[attr-defined]

        servicemanager.LogInfoMsg("Detec Server stopping")

    def SvcDoRun(self) -> None:
        """Called by the SCM to start the service."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        try:
            self._run_server()
        except Exception:
            tb = traceback.format_exc()
            logger.exception("Detec Server crashed")
            servicemanager.LogErrorMsg(f"Detec Server crashed:\n{tb}")
        finally:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STOPPED,
                (self._svc_name_, ""),
            )

    def _run_server(self) -> None:
        """Start uvicorn in a background thread and wait for the stop signal."""
        _load_env()

        os.chdir(str(_api_dir))

        import uvicorn
        from main import app

        host = os.environ.get("API_HOST", "0.0.0.0")
        port = int(os.environ.get("API_PORT", "8000"))

        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        self._server = server

        self._thread = threading.Thread(target=server.run, daemon=True)
        self._thread.start()

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogInfoMsg(
            f"Detec Server running on http://{host}:{port}"
        )

        # Block until SCM signals stop.
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)

        server.should_exit = True
        self._thread.join(timeout=10)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(DetecService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(DetecService)
