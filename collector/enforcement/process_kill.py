"""Process kill enforcement tactic.

Sends SIGTERM (graceful) then SIGKILL (force) to blocked tool
processes.  Requires appropriate OS permissions.

Before killing, the process command line is checked to confirm
it still belongs to the expected tool. This prevents accidental
kills caused by PID reuse.
"""

from __future__ import annotations

import logging
import os
import signal
import time

logger = logging.getLogger(__name__)

SIGTERM_GRACE_PERIOD = 3  # seconds to wait before SIGKILL


def _read_cmdline(pid: int) -> str | None:
    """Return the command line for *pid*, or None if unreadable."""
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()
    except OSError:
        pass
    try:
        import subprocess
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def kill_processes(
    pids: set[int],
    expected_pattern: str | None = None,
) -> list[int]:
    """Attempt to kill the given PIDs. Returns list of successfully killed PIDs.

    If *expected_pattern* is provided, each PID's command line is checked
    before sending signals. PIDs whose command line does not contain the
    pattern (case-insensitive) are skipped to guard against PID reuse.
    """
    killed: list[int] = []

    for pid in pids:
        if pid <= 1:
            continue

        if expected_pattern:
            cmdline = _read_cmdline(pid)
            if cmdline is None:
                logger.debug("PID %d: cannot read cmdline, skipping", pid)
                continue
            if expected_pattern.lower() not in cmdline.lower():
                logger.warning(
                    "PID %d: cmdline %r does not match expected pattern %r, skipping",
                    pid, cmdline[:120], expected_pattern,
                )
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
            os.kill(pid, 0)
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
