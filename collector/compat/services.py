"""Cross-platform service/daemon detection.

macOS:  launchctl list + brew services list
Linux:  systemctl is-active / is-enabled
Windows: psutil.win_service_get()
"""

from __future__ import annotations

import logging
import subprocess
import sys

import psutil

from .types import ServiceInfo

logger = logging.getLogger(__name__)

_PLATFORM = sys.platform


def get_service(name: str) -> ServiceInfo | None:
    """Check whether *name* is registered as an OS-managed service.

    Returns ``None`` when the service is not found at all.
    """
    if _PLATFORM == "darwin":
        return _get_service_macos(name)
    elif _PLATFORM == "win32":
        return _get_service_windows(name)
    else:
        return _get_service_linux(name)


# -- macOS -----------------------------------------------------------------

def _get_service_macos(name: str) -> ServiceInfo | None:
    """Check launchctl and Homebrew services."""
    try:
        proc = subprocess.run(
            ["launchctl", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if name.lower() in line.lower():
                    status = "running" if line.split()[0] != "-" else "stopped"
                    return ServiceInfo(name=name, status=status, start_type="auto")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    try:
        proc = subprocess.run(
            ["brew", "services", "list"],
            capture_output=True, text=True, timeout=5,
        )
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                if name.lower() in line.lower():
                    status = "running" if "started" in line.lower() else "stopped"
                    return ServiceInfo(name=name, status=status, start_type="auto")
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return None


# -- Linux -----------------------------------------------------------------

def _get_service_linux(name: str) -> ServiceInfo | None:
    """Check systemd service status."""
    try:
        active = subprocess.run(
            ["systemctl", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        enabled = subprocess.run(
            ["systemctl", "is-enabled", name],
            capture_output=True, text=True, timeout=5,
        )
        status = active.stdout.strip() if active.returncode == 0 else "stopped"
        if status == "active":
            status = "running"

        start_type = enabled.stdout.strip() if enabled.returncode == 0 else "unknown"
        if start_type == "enabled":
            start_type = "auto"
        elif start_type == "disabled":
            start_type = "disabled"
        else:
            start_type = "manual"

        if active.returncode != 0 and enabled.returncode != 0:
            return None

        return ServiceInfo(name=name, status=status, start_type=start_type)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


# -- Windows ---------------------------------------------------------------

def _get_service_windows(name: str) -> ServiceInfo | None:
    """Query Windows Service Control Manager via psutil."""
    try:
        svc = psutil.win_service_get(name)
        info = svc.as_dict()
        status_map = {"running": "running", "stopped": "stopped",
                       "start_pending": "running", "stop_pending": "stopped"}
        status = status_map.get(info.get("status", ""), info.get("status", "unknown"))
        start_map = {"auto": "auto", "manual": "manual", "disabled": "disabled"}
        start_type = start_map.get(info.get("start_type", ""), "unknown")
        return ServiceInfo(name=name, status=status, start_type=start_type)
    except (psutil.NoSuchProcess, AttributeError, Exception):
        return None
