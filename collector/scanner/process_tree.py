"""Process tree builder for behavioral anomaly detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

if TYPE_CHECKING:
    from telemetry.event_store import EventStore


@dataclass
class ProcessNode:
    pid: int
    ppid: int
    name: str
    cmdline: str
    children: list[ProcessNode] = field(default_factory=list)
    network_events: list[NetworkConnectEvent] = field(default_factory=list)
    file_events: list[FileChangeEvent] = field(default_factory=list)
    start_time: datetime | None = None
    username: str | None = None


def build_trees(store: EventStore) -> list[ProcessNode]:
    """Build process trees from recent telemetry.

    Returns root nodes (ppid=0, ppid=1, or ppid not in known PIDs).
    For duplicate PIDs, keeps the most recent event.
    """
    process_events = store.get_process_events()
    latest_by_pid: dict[int, ProcessExecEvent] = {}
    for e in process_events:
        if e.pid not in latest_by_pid or e.timestamp >= latest_by_pid[e.pid].timestamp:
            latest_by_pid[e.pid] = e

    net_by_pid: dict[int, list[NetworkConnectEvent]] = {}
    for e in store.get_network_events():
        net_by_pid.setdefault(e.pid, []).append(e)

    file_by_pid: dict[int, list[FileChangeEvent]] = {}
    for e in store.get_file_events():
        if e.pid is not None:
            file_by_pid.setdefault(e.pid, []).append(e)

    nodes: dict[int, ProcessNode] = {}
    for pid, e in latest_by_pid.items():
        nodes[pid] = ProcessNode(
            pid=e.pid,
            ppid=e.ppid,
            name=e.name,
            cmdline=e.cmdline,
            network_events=net_by_pid.get(pid, []),
            file_events=file_by_pid.get(pid, []),
            start_time=e.timestamp,
            username=e.username,
        )

    for node in nodes.values():
        if node.ppid in nodes:
            nodes[node.ppid].children.append(node)

    known_pids = set(nodes)
    return [
        n for n in nodes.values()
        if n.ppid <= 1 or n.ppid not in known_pids
    ]


def get_all_pids(tree: ProcessNode) -> set[int]:
    """Recursively collect all PIDs in a tree."""
    result = {tree.pid}
    for child in tree.children:
        result |= get_all_pids(child)
    return result


def tree_depth(node: ProcessNode) -> int:
    """Max depth of the process tree (root = 1)."""
    if not node.children:
        return 1
    return 1 + max(tree_depth(c) for c in node.children)


def _all_timestamps(node: ProcessNode) -> list[datetime]:
    timestamps: list[datetime] = []
    if node.start_time is not None:
        timestamps.append(node.start_time)
    for e in node.network_events:
        timestamps.append(e.timestamp)
    for e in node.file_events:
        timestamps.append(e.timestamp)
    for child in node.children:
        timestamps.extend(_all_timestamps(child))
    return timestamps


def tree_duration(node: ProcessNode) -> float:
    """Duration in seconds from earliest to latest event in the tree."""
    timestamps = _all_timestamps(node)
    if not timestamps:
        return 0.0
    return (max(timestamps) - min(timestamps)).total_seconds()
