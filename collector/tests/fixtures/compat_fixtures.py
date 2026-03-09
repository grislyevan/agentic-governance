"""Compat layer mock fixtures for scanner integration tests.

Provides ProcessInfo, ConnectionInfo, and ToolPaths return values that
replace pgrep/lsof/get_tool_paths in migrated scanners.
"""

from __future__ import annotations

from pathlib import Path

from compat import ConnectionInfo, ProcessInfo, ToolPaths


def make_tool_paths(home: Path, tool: str) -> ToolPaths:
    """Return ToolPaths for *tool* with paths under *home*.

    Supports "vscode" and "cursor" to match the layout used by
    create_cline_footprint and create_continue_footprint.
    """
    if tool.lower() == "vscode":
        return ToolPaths(
            config_dir=home / "Library" / "Application Support" / "Code",
            data_dir=home / ".vscode",
            extensions_dir=home / ".vscode" / "extensions",
        )
    if tool.lower() == "cursor":
        return ToolPaths(
            config_dir=home / "Library" / "Application Support" / "Cursor",
            data_dir=home / ".cursor",
            extensions_dir=home / ".cursor" / "extensions",
        )
    return ToolPaths()


def make_get_tool_paths(home: Path):
    """Return a get_tool_paths mock that uses *home*."""

    def _get_tool_paths(tool: str) -> ToolPaths:
        return make_tool_paths(home, tool)

    return _get_tool_paths


# ---------------------------------------------------------------------------
# Cline
# ---------------------------------------------------------------------------

CLINE_ACTIVE_PROCESSES: dict[str, list[ProcessInfo]] = {
    "Code": [],
    "Cursor": [
        ProcessInfo(
            pid=80010,
            name="Cursor",
            cmdline="/Applications/Cursor.app/Contents/Frameworks/Cursor Helper (Renderer).app --extensionHost",
            username="testuser",
        ),
    ],
}

CLINE_ACTIVE_CONNECTIONS: list[ConnectionInfo] = [
    ConnectionInfo(
        pid=80010,
        local_addr="192.168.1.10",
        local_port=55000,
        remote_addr="104.18.7.23",
        remote_port=443,
        status="ESTABLISHED",
    ),
]

CLINE_NOT_RUNNING_PROCESSES: dict[str, list[ProcessInfo]] = {
    "Code": [],
    "Cursor": [],
}

CLINE_NOT_RUNNING_CONNECTIONS: list[ConnectionInfo] = []


def make_cline_compat_mocks(home: Path, *, active: bool):
    """Return (find_processes_mock, get_connections_mock, get_tool_paths_mock)."""
    procs = CLINE_ACTIVE_PROCESSES if active else CLINE_NOT_RUNNING_PROCESSES
    conns = CLINE_ACTIVE_CONNECTIONS if active else CLINE_NOT_RUNNING_CONNECTIONS

    def _find_processes(name: str):
        return procs.get(name, [])

    def _get_connections(pids: set[int] | None = None):
        return [c for c in conns if c.pid in pids] if pids else conns

    return _find_processes, _get_connections, make_get_tool_paths(home)


# ---------------------------------------------------------------------------
# Continue
# ---------------------------------------------------------------------------

CONTINUE_ACTIVE_PROCESSES: dict[str, list[ProcessInfo]] = {
    "Code": [],
    "Cursor": [
        ProcessInfo(
            pid=60010,
            name="Cursor",
            cmdline="/Applications/Cursor.app/Contents/Frameworks/Cursor Helper (Renderer).app --extensionHost",
            username="testuser",
        ),
    ],
}

CONTINUE_ACTIVE_CONNECTIONS_OLLAMA: list[ConnectionInfo] = [
    ConnectionInfo(
        pid=60010,
        local_addr="127.0.0.1",
        local_port=54100,
        remote_addr="127.0.0.1",
        remote_port=11434,
        status="ESTABLISHED",
    ),
]

CONTINUE_APPROVED_ACTIVE_CONNECTIONS: list[ConnectionInfo] = [
    ConnectionInfo(
        pid=60010,
        local_addr="192.168.1.10",
        local_port=54100,
        remote_addr="104.18.7.23",
        remote_port=443,
        status="ESTABLISHED",
    ),
]

CONTINUE_NOT_RUNNING_PROCESSES: dict[str, list[ProcessInfo]] = {
    "Code": [],
    "Cursor": [],
}

CONTINUE_NOT_RUNNING_CONNECTIONS: list[ConnectionInfo] = []


# ---------------------------------------------------------------------------
# Aider
# ---------------------------------------------------------------------------

AIDER_ACTIVE_PROCESSES: list[ProcessInfo] = [
    ProcessInfo(
        pid=12345,
        name="aider",
        cmdline="python /usr/local/bin/aider --model gpt-4o test.py",
        username="testuser",
        ppid=12300,
    ),
]

AIDER_ACTIVE_PROCESSES_BY_PID: dict[int, ProcessInfo] = {
    12345: ProcessInfo(
        pid=12345,
        name="aider",
        cmdline="python /usr/local/bin/aider --model gpt-4o test.py",
        username="testuser",
        ppid=12300,
    ),
    12346: ProcessInfo(
        pid=12346,
        name="git",
        cmdline="git commit -m aider: fix tests",
        username="testuser",
        ppid=12345,
    ),
    12347: ProcessInfo(
        pid=12347,
        name="python",
        cmdline="python -m pytest",
        username="testuser",
        ppid=12345,
    ),
}

AIDER_ACTIVE_CHILD_PIDS: dict[int, list[int]] = {
    12345: [12346, 12347],
}

AIDER_ACTIVE_CONNECTIONS: list[ConnectionInfo] = [
    ConnectionInfo(
        pid=12345,
        local_addr="192.168.1.10",
        local_port=54321,
        remote_addr="104.18.7.23",
        remote_port=443,
        status="ESTABLISHED",
    ),
]


def make_aider_compat_mocks(*, active: bool):
    """Return (find_processes, get_child_pids, get_process_info, get_connections) mocks."""
    if active:
        def _find_processes(name: str):
            if name == "aider":
                return AIDER_ACTIVE_PROCESSES.copy()
            return []

        def _get_child_pids(pid: int):
            return AIDER_ACTIVE_CHILD_PIDS.get(pid, [])

        def _get_process_info(pid: int):
            return AIDER_ACTIVE_PROCESSES_BY_PID.get(pid)

        def _get_connections(pids: set[int] | None = None):
            return [c for c in AIDER_ACTIVE_CONNECTIONS if c.pid in pids] if pids else AIDER_ACTIVE_CONNECTIONS
    else:
        def _find_processes(name: str):
            return []

        def _get_child_pids(pid: int):
            return []

        def _get_process_info(pid: int):
            return None

        def _get_connections(pids: set[int] | None = None):
            return []

    return _find_processes, _get_child_pids, _get_process_info, _get_connections


# ---------------------------------------------------------------------------
# GPT-Pilot
# ---------------------------------------------------------------------------

GPT_PILOT_ACTIVE_PROCESSES: dict[str, list[ProcessInfo]] = {
    "gpt-pilot": [
        ProcessInfo(
            pid=70001,
            name="python",
            cmdline="python -m gpt_pilot",
            username="testuser",
            ppid=70000,
        ),
    ],
    "gpt_pilot": [],
    "pythagora": [],
}

GPT_PILOT_ACTIVE_PROCESSES_BY_PID: dict[int, ProcessInfo] = {
    70001: ProcessInfo(
        pid=70001,
        name="python",
        cmdline="python -m gpt_pilot",
        username="testuser",
        ppid=70000,
    ),
    70002: ProcessInfo(
        pid=70002,
        name="node",
        cmdline="node server.js",
        username="testuser",
        ppid=70001,
    ),
    70003: ProcessInfo(
        pid=70003,
        name="python",
        cmdline="python manage.py runserver",
        username="testuser",
        ppid=70001,
    ),
}

GPT_PILOT_ACTIVE_CHILD_PIDS: dict[int, list[int]] = {
    70001: [70002, 70003],
}

GPT_PILOT_ACTIVE_CONNECTIONS: list[ConnectionInfo] = [
    ConnectionInfo(
        pid=70001,
        local_addr="192.168.1.10",
        local_port=55432,
        remote_addr="104.18.7.23",
        remote_port=443,
        status="ESTABLISHED",
    ),
]


def make_gpt_pilot_compat_mocks(*, active: bool):
    """Return (find_processes, get_child_pids, get_process_info, get_connections) mocks."""
    if active:
        def _find_processes(name: str):
            return GPT_PILOT_ACTIVE_PROCESSES.get(name, []).copy()

        def _get_child_pids(pid: int):
            return GPT_PILOT_ACTIVE_CHILD_PIDS.get(pid, [])

        def _get_process_info(pid: int):
            return GPT_PILOT_ACTIVE_PROCESSES_BY_PID.get(pid)

        def _get_connections(pids: set[int] | None = None):
            return [c for c in GPT_PILOT_ACTIVE_CONNECTIONS if c.pid in pids] if pids else GPT_PILOT_ACTIVE_CONNECTIONS
    else:
        def _find_processes(name: str):
            return []

        def _get_child_pids(pid: int):
            return []

        def _get_process_info(pid: int):
            return None

        def _get_connections(pids: set[int] | None = None):
            return []

    return _find_processes, _get_child_pids, _get_process_info, _get_connections


def make_continue_compat_mocks(
    home: Path,
    *,
    active: bool,
    ollama_connection: bool = False,
):
    """Return (find_processes_mock, get_connections_mock, get_tool_paths_mock)."""
    procs = CONTINUE_ACTIVE_PROCESSES if active else CONTINUE_NOT_RUNNING_PROCESSES
    if active:
        conns = CONTINUE_ACTIVE_CONNECTIONS_OLLAMA if ollama_connection else CONTINUE_APPROVED_ACTIVE_CONNECTIONS
    else:
        conns = CONTINUE_NOT_RUNNING_CONNECTIONS

    def _find_processes(name: str):
        return procs.get(name, [])

    def _get_connections(pids: set[int] | None = None):
        return [c for c in conns if c.pid in pids] if pids else conns

    return _find_processes, _get_connections, make_get_tool_paths(home)
