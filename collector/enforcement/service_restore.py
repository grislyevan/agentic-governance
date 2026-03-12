"""Restore services disabled by anti-resurrection escalation.

When the enforcer's escalation logic disables a systemd unit or unloads
a launchd plist, the DisabledServiceTracker records the action. An admin
can later request restoration from the dashboard, which reaches the agent
via heartbeat response (HTTP) or COMMAND message (TCP). This module
implements the actual re-enablement.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.state import DisabledService, DisabledServiceTracker

logger = logging.getLogger(__name__)


def restore_service(svc: DisabledService, tracker: DisabledServiceTracker) -> bool:
    """Re-enable a single disabled service and remove it from the tracker.

    Returns True if the service was successfully restored.
    """
    system = platform.system()
    success = False

    if svc.service_type == "systemd" and system == "Linux":
        success = _restore_systemd(svc.unit_name)
    elif svc.service_type == "launchd" and system == "Darwin":
        success = _restore_launchd(svc.unit_name, svc.plist_path)
    else:
        logger.warning(
            "Cannot restore service %s: type=%s not supported on %s",
            svc.service_id, svc.service_type, system,
        )
        tracker.remove_service(svc.service_id)
        return False

    if success:
        tracker.remove_service(svc.service_id)
        logger.info("Restored service %s (%s)", svc.unit_name, svc.service_type)
    else:
        logger.warning("Failed to restore service %s (%s)", svc.unit_name, svc.service_type)

    return success


def restore_all(tracker: DisabledServiceTracker) -> dict[str, bool]:
    """Restore all disabled services. Returns {service_id: success}."""
    results: dict[str, bool] = {}
    for svc in tracker.get_disabled_services():
        results[svc.service_id] = restore_service(svc, tracker)
    return results


def restore_by_ids(
    service_ids: list[str],
    tracker: DisabledServiceTracker,
) -> dict[str, bool]:
    """Restore specific services by ID. Returns {service_id: success}."""
    results: dict[str, bool] = {}
    for sid in service_ids:
        svc = tracker.get_service(sid)
        if svc is None:
            logger.debug("Service %s not found in tracker, skipping", sid)
            results[sid] = False
            continue
        results[sid] = restore_service(svc, tracker)
    return results


def _restore_systemd(unit_name: str) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "enable", "--now", unit_name],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("Re-enabled systemd unit %s", unit_name)
            return True
        logger.warning(
            "systemctl enable %s failed (rc=%d): %s",
            unit_name, result.returncode, result.stderr.strip(),
        )
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.warning("Could not re-enable systemd unit %s: %s", unit_name, exc)
        return False


def _restore_launchd(label: str, plist_path: str | None) -> bool:
    if not plist_path or not Path(plist_path).is_file():
        logger.warning("Cannot restore launchd service %s: plist path missing or gone", label)
        return False

    try:
        result = subprocess.run(
            ["launchctl", "load", "-w", plist_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("Re-loaded launchd plist %s", plist_path)
            return True
        logger.warning(
            "launchctl load %s failed (rc=%d): %s",
            plist_path, result.returncode, result.stderr.strip(),
        )
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.warning("Could not reload launchd plist %s: %s", plist_path, exc)
        return False
