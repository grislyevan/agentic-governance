"""Network null-route enforcement tactic.

Blocks outbound network access for specific PIDs by adding firewall
rules.  Uses ``pfctl`` on macOS, ``iptables`` on Linux, and ``netsh
advfirewall`` on Windows.

IMPORTANT: Requires root/admin privileges.  Falls back to logging
if permissions are insufficient.

LIMITATION (Linux): Modern kernels removed iptables --pid-owner, so
blocking falls back to --uid-owner.  This affects ALL processes owned
by that UID, not just the target PID.  If the target tool runs under
a shared user account, other processes (browser, IDE, shell) will also
lose outbound connectivity until the rule is removed.  When cgroup v2
with net_cls is available, blocking scopes to the target PID only.
"""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

CGROUP_BASE = Path("/sys/fs/cgroup")
CGROUP_DIR_PREFIX = "detec-block"


def _classid_for_pid(pid: int) -> int:
    """Derive a unique net_cls classid from a PID (major=0x0010, minor=pid & 0xFFFF)."""
    return (0x0010 << 16) | (pid & 0xFFFF)


def block_outbound(pids: set[int]) -> bool:
    """Block outbound connections for the given PIDs.

    Returns True if at least one blocking rule was successfully applied.
    """
    system = platform.system()
    if system == "Darwin":
        return _block_macos(pids)
    if system == "Linux":
        return _block_linux(pids)
    if system == "Windows":
        return _block_windows(pids)
    logger.warning("Network blocking not supported on %s", system)
    return False


def unblock_outbound(pids: set[int]) -> bool:
    """Remove previously applied blocking rules."""
    system = platform.system()
    if system == "Darwin":
        return _unblock_macos(pids)
    if system == "Linux":
        return _unblock_linux(pids)
    if system == "Windows":
        return _unblock_windows(pids)
    return False


def _cgroup_v2_available() -> bool:
    """Check if cgroup v2 is available (unified hierarchy)."""
    return Path("/sys/fs/cgroup/cgroup.controllers").exists()


def _cgroup_v2_block(pid: int) -> bool:
    """Block a single PID's outbound traffic via cgroup v2 net_cls + iptables.

    Steps:
      1. Verify cgroup v2 unified hierarchy has net_cls controller.
      2. Enable net_cls in the subtree control if needed.
      3. Create ``/sys/fs/cgroup/detec-block-{pid}/`` and assign the PID.
      4. Write a unique classid derived from the PID.
      5. Add an iptables OUTPUT rule matching that classid.

    Returns True on success, False if cgroup v2/net_cls isn't usable
    (caller should fall back to UID-owner blocking).
    """
    if not _cgroup_v2_available():
        return False

    try:
        controllers_path = CGROUP_BASE / "cgroup.controllers"
        controllers = controllers_path.read_text().strip().split()
        if "net_cls" not in controllers:
            logger.warning(
                "cgroup v2 net_cls controller not available; "
                "using uid-owner fallback for PID %d",
                pid,
            )
            return False

        subtree_control = CGROUP_BASE / "cgroup.subtree_control"
        if subtree_control.exists():
            current = subtree_control.read_text().strip().split()
            if "net_cls" not in current:
                subtree_control.write_text("+net_cls\n")

        cgroup_dir = CGROUP_BASE / f"{CGROUP_DIR_PREFIX}-{pid}"
        cgroup_dir.mkdir(exist_ok=True)

        (cgroup_dir / "cgroup.procs").write_text(f"{pid}\n")

        classid = _classid_for_pid(pid)
        (cgroup_dir / "net_cls.classid").write_text(f"{classid}\n")

        comment = f"agentic-gov-block-cgroup-{pid}"
        result = subprocess.run(
            [
                "iptables", "-A", "OUTPUT",
                "-m", "cgroup", "--cgroup", str(classid),
                "-j", "DROP",
                "-m", "comment", "--comment", comment,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            logger.warning(
                "iptables cgroup rule failed for PID %d: %s",
                pid, result.stderr.strip(),
            )
            _remove_cgroup(pid)
            return False

        logger.info(
            "cgroup v2: blocked outbound for PID %d (classid 0x%08x)", pid, classid,
        )
        return True

    except Exception as exc:
        logger.debug("cgroup v2 block failed for PID %d: %s", pid, exc)
        _remove_cgroup(pid)
        return False


def _cgroup_v2_unblock(pid: int) -> bool:
    """Remove a cgroup-based network block for a PID.

    Removes the iptables rule, migrates processes back to the root cgroup,
    and deletes the cgroup directory.
    """
    cgroup_dir = CGROUP_BASE / f"{CGROUP_DIR_PREFIX}-{pid}"
    if not cgroup_dir.exists():
        return False

    classid = _classid_for_pid(pid)
    comment = f"agentic-gov-block-cgroup-{pid}"
    try:
        subprocess.run(
            [
                "iptables", "-D", "OUTPUT",
                "-m", "cgroup", "--cgroup", str(classid),
                "-j", "DROP",
                "-m", "comment", "--comment", comment,
            ],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
        logger.debug("Could not remove cgroup iptables rule for PID %d: %s", pid, exc)

    _remove_cgroup(pid)
    logger.info("cgroup v2: unblocked PID %d", pid)
    return True


def _remove_cgroup(pid: int) -> None:
    """Move processes back to the root cgroup and remove the per-PID cgroup dir.

    On a real cgroupfs, ``rmdir`` on the directory suffices because the kernel
    manages pseudo-files.  We also attempt to unlink children first so that the
    same code works on regular filesystems (e.g. in test fixtures).
    """
    cgroup_dir = CGROUP_BASE / f"{CGROUP_DIR_PREFIX}-{pid}"
    if not cgroup_dir.exists():
        return
    try:
        procs_file = cgroup_dir / "cgroup.procs"
        if procs_file.exists():
            for line in procs_file.read_text().strip().splitlines():
                try:
                    (CGROUP_BASE / "cgroup.procs").write_text(line.strip() + "\n")
                except OSError:
                    pass
        for child in cgroup_dir.iterdir():
            try:
                child.unlink()
            except OSError:
                pass
        cgroup_dir.rmdir()
    except OSError as exc:
        logger.debug("Could not remove cgroup dir for PID %d: %s", pid, exc)


def _get_exe_path_windows(pid: int) -> str | None:
    """Get the executable path for a PID on Windows."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.exe()
    except Exception:
        pass
    return None


def _block_linux(pids: set[int]) -> bool:
    """Use iptables owner match to drop outbound packets from specific PIDs.

    Note: iptables --pid-owner was removed in newer kernels.  We try
    _cgroup_v2_block first when cgroup v2 is available; if that returns
    False, we fall back to blocking by UID.  UID blocking affects ALL
    processes owned by that UID, not just the target process.
    """
    success = False
    for pid in pids:
        if _cgroup_v2_block(pid):
            success = True
            continue
        uid = _get_uid_linux(pid)
        if uid is None:
            continue
        logger.warning(
            "Blocking UID %d (from PID %d). This affects ALL processes "
            "owned by this UID, not just the target tool.",
            uid, pid,
        )
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
        if _cgroup_v2_unblock(pid):
            success = True
            continue
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


def _block_windows(pids: set[int]) -> bool:
    """Use netsh advfirewall to block outbound traffic by executable path."""
    success = False
    for pid in pids:
        exe_path = _get_exe_path_windows(pid)
        if not exe_path:
            continue
        rule_name = f"agentic-gov-block-{pid}"
        program_arg = f'program="{exe_path}"' if " " in exe_path else f"program={exe_path}"
        try:
            result = subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "add", "rule",
                    f"name={rule_name}",
                    "dir=out", "action=block",
                    program_arg,
                    "enable=yes",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("netsh: blocked outbound for %s (PID %d)", exe_path, pid)
                success = True
            else:
                logger.warning("netsh add rule failed: %s", result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
            logger.warning("netsh not available: %s", exc)
    return success


def _unblock_windows(pids: set[int]) -> bool:
    success = False
    for pid in pids:
        rule_name = f"agentic-gov-block-{pid}"
        try:
            result = subprocess.run(
                [
                    "netsh", "advfirewall", "firewall", "delete", "rule",
                    f"name={rule_name}",
                ],
                capture_output=True, text=True, timeout=10,
            )
            success = success or result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError) as exc:
            logger.debug("Could not remove netsh rule for PID %d: %s", pid, exc)
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
