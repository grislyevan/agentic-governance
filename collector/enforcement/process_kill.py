"""Process kill enforcement tactic.

Sends SIGTERM (graceful) then SIGKILL (force) to blocked tool
processes.  Requires appropriate OS permissions.
"""

from __future__ import annotations

import logging
import os
import signal
import time

logger = logging.getLogger(__name__)

SIGTERM_GRACE_PERIOD = 3  # seconds to wait before SIGKILL


def kill_processes(pids: set[int]) -> list[int]:
    """Attempt to kill the given PIDs. Returns list of successfully killed PIDs."""
    killed: list[int] = []

    for pid in pids:
        if pid <= 1:
            continue
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to PID %d", pid)
        except ProcessLookupError:
            logger.debug("PID %d already gone", pid)
            killed.append(pid)
            continue
        except PermissionError:
            logger.warning("No permission to kill PID %d", pid)
            continue

    if not pids:
        return killed

    time.sleep(SIGTERM_GRACE_PERIOD)

    for pid in pids:
        if pid <= 1 or pid in killed:
            continue
        try:
            os.kill(pid, 0)  # check if still alive
        except ProcessLookupError:
            killed.append(pid)
            continue
        except PermissionError:
            continue

        try:
            os.kill(pid, signal.SIGKILL)
            logger.info("Sent SIGKILL to PID %d", pid)
            killed.append(pid)
        except (ProcessLookupError, PermissionError) as exc:
            logger.warning("SIGKILL failed for PID %d: %s", pid, exc)

    return killed
