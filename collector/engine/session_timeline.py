"""Build session timelines from EventStore and tool PIDs.

Produces an ordered list of (at, label, type) entries for agent session
narratives: LLM request, bash <cmd>, write <file>, etc.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from telemetry.event_store import EventStore
from scanner.process_tree import build_trees, get_all_pids

if TYPE_CHECKING:
    from telemetry.event_store import FileChangeEvent, NetworkConnectEvent, ProcessExecEvent

_SHELL_NAMES: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "fish", "csh", "tcsh", "dash",
    "cmd", "powershell", "pwsh",
})

_LLM_HOST_PATTERNS: tuple[str, ...] = (
    "anthropic", "openai", "api.anthropic", "api.openai",
    "ollama", "localhost",
)

_MAX_TIMELINE_ENTRIES = 100
_MAX_LABEL_LEN = 120


@dataclass
class TimelineEntry:
    """One entry in a session timeline."""

    at: str   # HH:MM:SS or ISO8601
    label: str
    type: str  # llm, shell_exec, file_write, file_delete, file_modified, network, exec


def _basename(name: str) -> str:
    """Process name without path or .exe."""
    n = os.path.basename(name).lower()
    if n.endswith(".exe"):
        n = n[:-4]
    return n


def _truncate(s: str, max_len: int = _MAX_LABEL_LEN) -> str:
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _process_to_entry(e: "ProcessExecEvent") -> TimelineEntry:
    ts = e.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    at_str = ts.strftime("%H:%M:%S")
    name_base = _basename(e.name)
    is_shell = name_base in _SHELL_NAMES
    if is_shell:
        cmd = (e.cmdline or "").strip()
        if cmd:
            parts = cmd.split()
            if len(parts) >= 2 and parts[0].endswith(name_base) or parts[0] == name_base:
                label = f"{name_base} {' '.join(parts[1:5])}".strip()
            else:
                label = f"{name_base} {cmd[:80]}".strip()
        else:
            label = name_base
        entry_type = "shell_exec"
    else:
        label = e.name or e.cmdline or "exec"
        if len(label) > 60:
            label = label[:57] + "..."
        entry_type = "exec"
    return TimelineEntry(at=_truncate(at_str, 32), label=_truncate(label), type=entry_type)


def _file_to_entry(e: "FileChangeEvent") -> TimelineEntry:
    ts = e.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    at_str = ts.strftime("%H:%M:%S")
    base = os.path.basename(e.path) or e.path
    if e.action in ("created", "modified"):
        label = f"write {base}" if e.action == "created" else f"modified {base}"
        entry_type = "file_write" if e.action == "created" else "file_modified"
    elif e.action == "deleted":
        label = f"delete {base}"
        entry_type = "file_delete"
    else:
        label = f"{e.action} {base}"
        entry_type = "file_modified"
    return TimelineEntry(at=_truncate(at_str, 32), label=_truncate(label), type=entry_type)


def _network_to_entry(e: "NetworkConnectEvent") -> TimelineEntry:
    ts = e.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    at_str = ts.strftime("%H:%M:%S")
    addr = (e.remote_addr or "") + (e.sni or "")
    addr_lower = addr.lower()
    is_llm = any(p in addr_lower for p in _LLM_HOST_PATTERNS)
    if is_llm:
        label = "LLM request"
        entry_type = "llm"
    else:
        host = e.remote_addr or e.sni or "unknown"
        label = f"connect to {host}"
        entry_type = "network"
    return TimelineEntry(at=_truncate(at_str, 32), label=_truncate(label), type=entry_type)


def _expand_pids_to_trees(store: "EventStore", tool_pids: set[int]) -> set[int]:
    """Expand tool_pids to include all PIDs in trees that contain any of them."""
    if not tool_pids:
        return set()
    trees = build_trees(store)
    expanded: set[int] = set()
    for tree in trees:
        tree_pids = get_all_pids(tree)
        if tree_pids & tool_pids:
            expanded |= tree_pids
    return expanded if expanded else tool_pids


def build_session_timeline(
    store: "EventStore",
    tool_name: str,
    tool_pids: set[int],
    *,
    expand_tree: bool = True,
    max_entries: int = _MAX_TIMELINE_ENTRIES,
) -> list[dict[str, str]]:
    """Build a sorted list of timeline entries for the given tool and PIDs.

    Args:
        store: EventStore with process, network, and file events.
        tool_name: Tool name (for logging; not used in output).
        tool_pids: PIDs attributed to the tool (from scan evidence).
        expand_tree: If True, expand to full process tree PIDs so child
            processes (e.g. bash spawned by Cursor) are included.
        max_entries: Maximum number of entries to return (oldest dropped).

    Returns:
        List of dicts with keys "at", "label", "type", sorted by time.
        Empty if no PIDs or no events in store for those PIDs.
    """
    pids = _expand_pids_to_trees(store, tool_pids) if expand_tree and tool_pids else tool_pids
    if not pids:
        return []

    process_events = store.get_process_events()
    network_events = store.get_network_events()
    file_events = store.get_file_events()

    entries: list[tuple[datetime, TimelineEntry]] = []

    for e in process_events:
        if e.pid in pids:
            entries.append((e.timestamp, _process_to_entry(e)))

    for e in network_events:
        if e.pid in pids:
            entries.append((e.timestamp, _network_to_entry(e)))

    for e in file_events:
        if e.pid is not None and e.pid in pids:
            entries.append((e.timestamp, _file_to_entry(e)))

    entries.sort(key=lambda x: x[0])
    if len(entries) > max_entries:
        entries = entries[-max_entries:]

    return [
        {"at": e.at, "label": e.label, "type": e.type}
        for _, e in entries
    ]
