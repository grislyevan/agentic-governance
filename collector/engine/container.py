"""Container isolation detection.

Determines whether a process is running inside a Docker/OCI container.
Used by the ISO-001 policy rule to enforce that Class C agents only
run inside containers where their blast radius is naturally limited.
"""

from __future__ import annotations

import logging
import os
import platform
import subprocess

logger = logging.getLogger(__name__)


def is_containerized(pid: int | None = None) -> bool:
    """Check if a process is running inside a container.

    If *pid* is None, checks the current process.

    Detection methods:
    - Linux: inspect /proc/{pid}/cgroup for docker/containerd/lxc markers
    - macOS: check parent process chain for com.docker
    - Fallback: check for /.dockerenv file
    """
    system = platform.system()

    if system == "Linux":
        return _check_linux_cgroup(pid)

    if system == "Darwin":
        return _check_macos_docker(pid)

    return False


def is_child_of_docker(pid: int) -> bool:
    """Walk the process tree upward to check if any ancestor is Docker."""
    system = platform.system()

    if system == "Linux":
        return _check_linux_cgroup(pid)

    if system == "Darwin":
        return _check_macos_docker(pid)

    return False


def _check_linux_cgroup(pid: int | None) -> bool:
    """Check /proc/{pid}/cgroup for container runtime markers."""
    target_pid = pid or os.getpid()

    if os.path.exists("/.dockerenv"):
        return True

    cgroup_path = f"/proc/{target_pid}/cgroup"
    try:
        with open(cgroup_path) as f:
            content = f.read()
        markers = ("docker", "containerd", "lxc", "kubepods", "crio")
        return any(m in content for m in markers)
    except (OSError, PermissionError) as exc:
        logger.debug("Could not read cgroup file %s: %s", cgroup_path, exc)

    mountinfo_path = f"/proc/{target_pid}/mountinfo"
    try:
        with open(mountinfo_path) as f:
            content = f.read()
        return "docker" in content or "overlay" in content
    except (OSError, PermissionError) as exc:
        logger.debug("Could not read mountinfo file %s: %s", mountinfo_path, exc)

    return False


def _check_macos_docker(pid: int | None) -> bool:
    """On macOS, Docker runs processes inside a Linux VM.

    A process on the macOS host is never truly "inside" Docker.
    We check if the process was launched by Docker Desktop (parent
    chain includes com.docker) or if docker.sock is available.
    """
    target_pid = pid or os.getpid()

    try:
        current = target_pid
        visited: set[int] = set()
        while current > 1 and current not in visited:
            visited.add(current)
            result = subprocess.run(
                ["ps", "-p", str(current), "-o", "ppid=,comm="],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode != 0:
                break
            parts = result.stdout.strip().split(None, 1)
            if len(parts) < 2:
                break
            ppid_str, comm = parts
            if "docker" in comm.lower() or "com.docker" in comm.lower():
                return True
            try:
                current = int(ppid_str)
            except ValueError:
                break
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.debug("Docker ancestry check via ps failed: %s", exc)

    return os.path.exists("/var/run/docker.sock")


def is_devcontainer(pid: int | None = None) -> bool:
    """Check if the process is running in a Dev Container (VS Code / devcontainer) context.

    Detection methods:
    - Environment variable DEVCONTAINER (set by VS Code when attached to a container)
    - Environment variable DEVCONTAINER_ID (devcontainer CLI)
    - Linux: /.devcontainer or /run/.devcontainer marker when present in container
    If *pid* is not None, only the current process env is checked (no cross-process env read).
    """
    if pid is not None and pid != os.getpid():
        return False
    if os.environ.get("DEVCONTAINER") not in (None, "", "0"):
        return True
    if os.environ.get("DEVCONTAINER_ID"):
        return True
    if platform.system() == "Linux" and (
        os.path.exists("/.devcontainer") or os.path.exists("/run/.devcontainer")
    ):
        return True
    return False


def is_remote_dev_context() -> bool:
    """Check if the current process appears to be in a remote development context.

    Detection methods:
    - VS Code remote: VSCODE_IPC_HOOK_CLI, REMOTE_CONTAINERS_* env vars
    - SSH remote / Codespaces: CODESPACES, SSH_CONNECTION
    Used for reporting and documentation; host telemetry may be partial in these contexts.
    """
    if os.environ.get("VSCODE_IPC_HOOK_CLI"):
        return True
    if os.environ.get("REMOTE_CONTAINERS") == "true":
        return True
    if os.environ.get("CODESPACES") == "true":
        return True
    if os.environ.get("SSH_CONNECTION") and os.environ.get("VSCODE_IPC_HOOK_CLI"):
        return True
    return False
