"""Process kill enforcement tactic.

Sends SIGTERM (graceful) then SIGKILL (force) to blocked tool
processes and their descendants. Requires appropriate OS permissions.

Before killing, the process command line is checked to confirm
it still belongs to the expected tool. This prevents accidental
kills caused by PID reuse.
"""

from __future__ import annotations

import logging
import os
import signal
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SIGTERM_GRACE_PERIOD = 3


def _read_cmdline(pid: int) -> str | None:
    """Return the command line for *pid*, or None if unreadable.

    Fallback when psutil is unavailable (e.g. Windows without psutil).
    """
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


@dataclass
class KillResult:
    pid: int
    success: bool
    killed_pids: list[int] = field(default_factory=list)
    detail: str = ""


def kill_process_tree(
    pid: int,
    expected_pattern: str | None = None,
    grace_period: float = SIGTERM_GRACE_PERIOD,
) -> KillResult:
    """Kill a process and all its descendants.

    Children are killed first (leaf to root), then the parent.
    Sends SIGTERM, waits grace_period, then SIGKILL for survivors.
    """
    if pid <= 1:
        return KillResult(pid=pid, success=False, detail="skipped: PID <= 1")

    try:
        import psutil
    except ImportError:
        return _kill_process_tree_fallback(pid, expected_pattern, grace_period)

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return KillResult(pid=pid, success=True, detail="already gone")

    if expected_pattern:
        try:
            cmdline = " ".join(parent.cmdline() or [])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return KillResult(pid=pid, success=False, detail="cannot read cmdline")
        if expected_pattern.lower() not in cmdline.lower():
            return KillResult(
                pid=pid,
                success=False,
                detail="cmdline mismatch, PID reuse suspected",
            )

    children = parent.children(recursive=True)
    all_pids = [c.pid for c in children] + [pid]

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        pass

    for p in children + [parent]:
        try:
            p.send_signal(signal.SIGTERM)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    gone, alive = psutil.wait_procs(children + [parent], timeout=grace_period)

    for p in alive:
        try:
            p.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    logger.info("Killed process tree for PID %d: %d processes", pid, len(all_pids))
    return KillResult(
        pid=pid,
        success=True,
        killed_pids=all_pids,
        detail=f"killed {len(all_pids)} processes",
    )


def _kill_process_tree_fallback(
    pid: int,
    expected_pattern: str | None,
    grace_period: float,
) -> KillResult:
    """Fallback when psutil is unavailable: kill only the given PID."""
    if expected_pattern:
        cmdline = _read_cmdline(pid)
        if cmdline is None:
            return KillResult(pid=pid, success=False, detail="cannot read cmdline")
        if expected_pattern.lower() not in cmdline.lower():
            return KillResult(
                pid=pid,
                success=False,
                detail="cmdline mismatch, PID reuse suspected",
            )

    import os
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return KillResult(pid=pid, success=True, detail="already gone")
    except PermissionError:
        return KillResult(pid=pid, success=False, detail="permission denied")

    time.sleep(grace_period)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return KillResult(pid=pid, success=True, killed_pids=[pid], detail="killed 1 process")
    except PermissionError:
        return KillResult(pid=pid, success=False, detail="permission denied")

    try:
        os.kill(pid, signal.SIGKILL)
        return KillResult(pid=pid, success=True, killed_pids=[pid], detail="killed 1 process")
    except (ProcessLookupError, PermissionError):
        return KillResult(pid=pid, success=False, detail="SIGKILL failed")


def kill_processes(
    pids: set[int] | Iterable[int],
    expected_pattern: str | None = None,
) -> list[int]:
    """Attempt to kill the given PIDs. Returns list of successfully killed PIDs.

    Thin wrapper: calls kill_process_tree() for each PID. Kept for backwards
    compatibility.
    """
    killed: list[int] = []
    for pid in pids:
        if pid <= 1:
            continue
        result = kill_process_tree(pid, expected_pattern=expected_pattern)
        if result.success and result.killed_pids:
            killed.extend(result.killed_pids)
    return list(dict.fromkeys(killed))
