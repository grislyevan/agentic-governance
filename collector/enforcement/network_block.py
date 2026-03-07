"""Network null-route enforcement tactic.

Blocks outbound network access for specific PIDs by adding firewall
rules.  Uses ``pfctl`` on macOS and ``iptables`` on Linux.

IMPORTANT: Requires root/admin privileges.  Falls back to logging
if permissions are insufficient.
"""

from __future__ import annotations

import logging
import platform
import subprocess

logger = logging.getLogger(__name__)


def block_outbound(pids: set[int]) -> bool:
    """Block outbound connections for the given PIDs.

    Returns True if at least one blocking rule was successfully applied.
    """
    system = platform.system()
    if system == "Darwin":
        return _block_macos(pids)
    if system == "Linux":
        return _block_linux(pids)
    logger.warning("Network blocking not supported on %s", system)
    return False


def unblock_outbound(pids: set[int]) -> bool:
    """Remove previously applied blocking rules."""
    system = platform.system()
    if system == "Darwin":
        return _unblock_macos(pids)
    if system == "Linux":
        return _unblock_linux(pids)
    return False


def _block_linux(pids: set[int]) -> bool:
    """Use iptables owner match to drop outbound packets from specific PIDs.

    Note: iptables --pid-owner was removed in newer kernels.  We fall
    back to blocking by UID if the process owner can be determined via
    /proc/{pid}/status.
    """
    success = False
    for pid in pids:
        uid = _get_uid_linux(pid)
        if uid is None:
            continue
        try:
            result = subprocess.run(
                [
                    "iptables", "-A", "OUTPUT",
                    "-m", "owner", "--uid-owner", str(uid),
                    "-j", "DROP",
                    "-m", "comment", "--comment", f"agentic-gov-block-pid-{pid}",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("iptables: blocked outbound for UID %d (PID %d)", uid, pid)
                success = True
            else:
                logger.warning("iptables failed: %s", result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
            logger.warning("iptables not available: %s", exc)
    return success


def _unblock_linux(pids: set[int]) -> bool:
    success = False
    for pid in pids:
        uid = _get_uid_linux(pid)
        if uid is None:
            continue
        try:
            result = subprocess.run(
                [
                    "iptables", "-D", "OUTPUT",
                    "-m", "owner", "--uid-owner", str(uid),
                    "-j", "DROP",
                    "-m", "comment", "--comment", f"agentic-gov-block-pid-{pid}",
                ],
                capture_output=True, text=True, timeout=10,
            )
            success = success or result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
            logger.debug("Could not remove iptables block rule for PID %d: %s", pid, exc)
    return success


def _get_uid_linux(pid: int) -> int | None:
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("Uid:"):
                    return int(line.split()[1])
    except (OSError, ValueError, IndexError) as exc:
        logger.debug("Could not read UID from /proc/%d/status: %s", pid, exc)
    return None


def _block_macos(pids: set[int]) -> bool:
    """Use pf (packet filter) anchors on macOS.

    Adds a ``block drop out`` rule to a dedicated anchor.
    Requires root.
    """
    rules: list[str] = []
    for pid in pids:
        user = _get_user_macos(pid)
        if user:
            rules.append(f"block drop out quick proto tcp from any to any user {user}")

    if not rules:
        return False

    anchor_name = "com.agentic-gov.block"
    rule_text = "\n".join(rules) + "\n"

    try:
        load = subprocess.run(
            ["pfctl", "-a", anchor_name, "-f", "-"],
            input=rule_text, capture_output=True, text=True, timeout=10,
        )
        if load.returncode == 0:
            logger.info("pfctl: loaded %d blocking rules into anchor %s", len(rules), anchor_name)
            return True
        logger.warning("pfctl load failed: %s", load.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.warning("pfctl not available: %s", exc)
    return False


def _unblock_macos(pids: set[int]) -> bool:
    anchor_name = "com.agentic-gov.block"
    try:
        result = subprocess.run(
            ["pfctl", "-a", anchor_name, "-F", "rules"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
        return False


def _get_user_macos(pid: int) -> str | None:
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "user="],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.debug("Could not get user for PID %d via ps: %s", pid, exc)
    return None
