"""Cross-platform process enumeration backed by psutil."""

from __future__ import annotations

import logging
import re

import psutil

from .types import ProcessInfo

logger = logging.getLogger(__name__)


def find_processes(name_pattern: str) -> list[ProcessInfo]:
    """Return processes whose name or command line matches *name_pattern*.

    The pattern is matched case-sensitively against both the process name
    and the full command-line string (joined with spaces).  This mirrors the
    behaviour of ``pgrep -fl <pattern>`` on Unix.
    """
    results: list[ProcessInfo] = []
    regex = re.compile(name_pattern)

    for proc in psutil.process_iter(["pid", "name", "cmdline", "username", "ppid"]):
        try:
            info = proc.info  # type: ignore[attr-defined]
            pname: str = info.get("name") or ""
            cmdline_parts: list[str] = info.get("cmdline") or []
            cmdline = " ".join(cmdline_parts)

            if not (regex.search(pname) or regex.search(cmdline)):
                continue

            results.append(ProcessInfo(
                pid=info["pid"],
                name=pname,
                cmdline=cmdline,
                username=info.get("username"),
                ppid=info.get("ppid"),
            ))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return results


def get_process_info(pid: int) -> ProcessInfo | None:
    """Return details for a single PID, or ``None`` if inaccessible."""
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            return ProcessInfo(
                pid=proc.pid,
                name=proc.name(),
                cmdline=" ".join(proc.cmdline()),
                username=_safe_username(proc),
                ppid=proc.ppid(),
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def get_child_pids(pid: int) -> list[int]:
    """Return PIDs of direct children of *pid*."""
    try:
        parent = psutil.Process(pid)
        return [c.pid for c in parent.children(recursive=False)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return []


def _safe_username(proc: psutil.Process) -> str | None:
    """Retrieve username without raising on AccessDenied."""
    try:
        return proc.username()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        return None
