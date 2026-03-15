"""Build session timelines from EventStore and tool PIDs.

Produces an ordered list of (at, label, type) entries for agent session
narratives: LLM request, bash <cmd>, write <file>, git commit, etc.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

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

# Git subcommands to detect and label as type "git"
_GIT_SUBCOMMANDS: frozenset[str] = frozenset({
    "add", "commit", "push", "clone", "pull", "merge", "rebase", "checkout",
})

_MAX_TIMELINE_ENTRIES = 100
_MAX_LABEL_LEN = 120


@dataclass
class TimelineEntry:
    """One entry in a session timeline."""

    at: str   # HH:MM:SS or ISO8601
    label: str
    type: str  # llm, shell_exec, file_write, file_delete, file_modified, network, exec, git, sequence_start, sequence_end
    process_name: str | None = None
    pid: int | None = None
    parent_pid: int | None = None
    parent_process_name: str | None = None


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


def _pid_to_name_map(process_events: list["ProcessExecEvent"]) -> dict[int, str]:
    """Build pid -> process name (basename) from latest event per PID."""
    latest: dict[int, "ProcessExecEvent"] = {}
    for e in process_events:
        if e.pid not in latest or e.timestamp >= latest[e.pid].timestamp:
            latest[e.pid] = e
    return {pid: _basename(e.name) for pid, e in latest.items()}


def _detect_git_subcommand(cmdline: str) -> str | None:
    """If cmdline is a git subcommand, return 'git <subcommand>'; else None."""
    cmd = (cmdline or "").strip()
    if not cmd:
        return None
    parts = re.split(r"\s+", cmd, maxsplit=2)
    if not parts or _basename(parts[0]) != "git":
        return None
    if len(parts) >= 2 and parts[1].lower() in _GIT_SUBCOMMANDS:
        return f"git {parts[1].lower()}"
    return None


def _process_to_entry(
    e: "ProcessExecEvent",
    pid_to_name: dict[int, str],
) -> TimelineEntry:
    ts = e.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    at_str = ts.strftime("%H:%M:%S")
    name_base = _basename(e.name)
    parent_name = pid_to_name.get(e.ppid) if e.ppid else None

    git_label = _detect_git_subcommand(e.cmdline or "")
    if git_label is not None:
        return TimelineEntry(
            at=_truncate(at_str, 32),
            label=git_label,
            type="git",
            process_name=name_base,
            pid=e.pid,
            parent_pid=e.ppid,
            parent_process_name=parent_name,
        )

    is_shell = name_base in _SHELL_NAMES
    if is_shell:
        cmd = (e.cmdline or "").strip()
        if cmd:
            parts = cmd.split()
            if len(parts) >= 2 and (parts[0].endswith(name_base) or parts[0] == name_base):
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
    return TimelineEntry(
        at=_truncate(at_str, 32),
        label=_truncate(label),
        type=entry_type,
        process_name=name_base,
        pid=e.pid,
        parent_pid=e.ppid,
        parent_process_name=parent_name,
    )


def _file_to_entry(
    e: "FileChangeEvent",
    pid_to_name: dict[int, str],
) -> TimelineEntry:
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
    process_name = None
    if e.process_name:
        process_name = _basename(e.process_name)
    elif e.pid is not None:
        process_name = pid_to_name.get(e.pid)
    return TimelineEntry(
        at=_truncate(at_str, 32),
        label=_truncate(label),
        type=entry_type,
        process_name=process_name,
        pid=e.pid,
    )


def _network_to_entry(
    e: "NetworkConnectEvent",
    pid_to_name: dict[int, str],
) -> TimelineEntry:
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
    process_name = _basename(e.process_name) if e.process_name else pid_to_name.get(e.pid)
    return TimelineEntry(
        at=_truncate(at_str, 32),
        label=_truncate(label),
        type=entry_type,
        process_name=process_name,
        pid=e.pid,
    )


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


def _insert_sequence_boundaries(entries: list[TimelineEntry]) -> list[TimelineEntry]:
    """Insert [execution sequence] / [end sequence] markers after each LLM block."""
    if not entries:
        return []
    result: list[TimelineEntry] = []
    seen_llm = False
    for entry in entries:
        if entry.type == "llm":
            if seen_llm:
                result.append(
                    TimelineEntry(
                        at=entry.at,
                        label="[end sequence]",
                        type="sequence_end",
                    )
                )
            seen_llm = True
            result.append(entry)
            result.append(
                TimelineEntry(
                    at=entry.at,
                    label="[execution sequence]",
                    type="sequence_start",
                )
            )
        else:
            result.append(entry)
    if seen_llm:
        result.append(
            TimelineEntry(
                at=result[-1].at if result else "",
                label="[end sequence]",
                type="sequence_end",
            )
        )
    return result


def _entry_to_dict(e: TimelineEntry) -> dict[str, Any]:
    """Convert TimelineEntry to dict for API/event payload."""
    out: dict[str, Any] = {"at": e.at, "label": e.label, "type": e.type}
    if e.process_name is not None:
        out["process_name"] = e.process_name
    if e.pid is not None:
        out["pid"] = e.pid
    if e.parent_pid is not None:
        out["parent_pid"] = e.parent_pid
    if e.parent_process_name is not None:
        out["parent_process_name"] = e.parent_process_name
    return out


def timeline_summary_from_entries(entries: list[dict[str, Any]]) -> dict[str, int]:
    """Compute counts by type from timeline entries. Omits sequence_start/sequence_end."""
    skip_types = frozenset({"sequence_start", "sequence_end"})
    counts: dict[str, int] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        t = e.get("type")
        if t is None or t in skip_types:
            continue
        counts[t] = counts.get(t, 0) + 1
    return counts


def build_session_timeline(
    store: "EventStore",
    tool_name: str,
    tool_pids: set[int],
    *,
    expand_tree: bool = True,
    max_entries: int = _MAX_TIMELINE_ENTRIES,
) -> list[dict[str, Any]]:
    """Build a sorted list of timeline entries for the given tool and PIDs.

    Args:
        store: EventStore with process, network, and file events.
        tool_name: Tool name (for logging; not used in output).
        tool_pids: PIDs attributed to the tool (from scan evidence).
        expand_tree: If True, expand to full process tree PIDs so child
            processes (e.g. bash spawned by Cursor) are included.
        max_entries: Maximum number of entries to return (oldest dropped).

    Returns:
        List of dicts with keys "at", "label", "type", and optionally
        process_name, pid, parent_pid, parent_process_name. Sorted by
        (timestamp, insertion index). May include sequence_start/sequence_end
        boundary entries.
    """
    pids = _expand_pids_to_trees(store, tool_pids) if expand_tree and tool_pids else tool_pids
    if not pids:
        return []

    process_events = store.get_process_events()
    network_events = store.get_network_events()
    file_events = store.get_file_events()

    pid_to_name = _pid_to_name_map(process_events)

    entries_with_index: list[tuple[datetime, int, TimelineEntry]] = []
    idx = 0
    for e in process_events:
        if e.pid in pids:
            entries_with_index.append((e.timestamp, idx, _process_to_entry(e, pid_to_name)))
            idx += 1
    for e in network_events:
        if e.pid in pids:
            entries_with_index.append((e.timestamp, idx, _network_to_entry(e, pid_to_name)))
            idx += 1
    for e in file_events:
        if e.pid is not None and e.pid in pids:
            entries_with_index.append((e.timestamp, idx, _file_to_entry(e, pid_to_name)))
            idx += 1

    entries_with_index.sort(key=lambda x: (x[0], x[1]))
    if len(entries_with_index) > max_entries:
        entries_with_index = entries_with_index[-max_entries:]

    entries_only = [e for _, _, e in entries_with_index]
    with_boundaries = _insert_sequence_boundaries(entries_only)

    return [_entry_to_dict(e) for e in with_boundaries]
