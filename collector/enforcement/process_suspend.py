"""SIGSTOP/SIGCONT primitives for process suspension during approval holds.

Provides OS-level process suspension so that an autonomous agent cannot
continue executing (writing code, pushing commits, exfiltrating data) while
an approval decision is pending.

Only works on Unix (macOS/Linux). Windows is not supported — calls degrade
gracefully to no-ops.

Safety notes:
  - Sends to individual PIDs, NOT process groups (avoids freezing terminals).
  - SIGSTOP cannot be caught or ignored by the target process.
  - SIGCONT is safe to send to already-running processes (no-op).
  - A suspended process must NOT be counted as "killed" by the resurrection
    detector — callers must avoid recording SIGSTOP in kill history.
"""

from __future__ import annotations

import logging
import os
import platform
import signal

logger = logging.getLogger(__name__)


def suspend_processes(pids: set[int]) -> dict[int, bool]:
    """Send SIGSTOP to each PID. Returns {pid: success}.

    Only works on Unix (macOS/Linux). Windows is not supported.
    Sends to individual PIDs, NOT process groups (avoids freezing terminal).
    """
    if platform.system() == "Windows":
        logger.warning("SIGSTOP not available on Windows; skipping suspension")
        return {pid: False for pid in pids}

    results: dict[int, bool] = {}
    for pid in pids:
        if pid <= 1:
            logger.warning("Refusing to SIGSTOP PID %d (system process)", pid)
            results[pid] = False
            continue
        try:
            os.kill(pid, signal.SIGSTOP)
            results[pid] = True
            logger.info("Suspended PID %d (SIGSTOP)", pid)
        except ProcessLookupError:
            logger.warning("PID %d not found; skipping SIGSTOP", pid)
            results[pid] = False
        except PermissionError:
            logger.warning("No permission to SIGSTOP PID %d", pid)
            results[pid] = False
        except OSError as exc:
            logger.warning("Failed to SIGSTOP PID %d: %s", pid, exc)
            results[pid] = False
    return results


def resume_processes(pids: set[int]) -> dict[int, bool]:
    """Send SIGCONT to each PID. Returns {pid: success}.

    Safe to call even if PID wasn't stopped — SIGCONT is a no-op on running processes.
    """
    if platform.system() == "Windows":
        return {pid: False for pid in pids}

    results: dict[int, bool] = {}
    for pid in pids:
        try:
            os.kill(pid, signal.SIGCONT)
            results[pid] = True
            logger.info("Resumed PID %d (SIGCONT)", pid)
        except (ProcessLookupError, PermissionError, OSError) as exc:
            logger.warning("Failed to SIGCONT PID %d: %s", pid, exc)
            results[pid] = False
    return results
