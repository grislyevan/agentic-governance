"""Tests for session timeline reconstruction."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

from engine.session_timeline import build_session_timeline, timeline_summary_from_entries


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ts_offset(seconds_ago: int) -> datetime:
    """Timestamp within retention window (120s default)."""
    return _now() - timedelta(seconds=seconds_ago)


def test_empty_pids_returns_empty() -> None:
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(10),
            pid=100,
            ppid=1,
            name="bash",
            cmdline="bash npm install",
            source="polling",
        )
    )
    result = build_session_timeline(store, "Cursor", set(), expand_tree=False)
    assert result == []


def test_pid_filtering_only_includes_tool_pids() -> None:
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(60),
            pid=100,
            ppid=1,
            name="bash",
            cmdline="bash npm install",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(50),
            pid=999,
            ppid=1,
            name="bash",
            cmdline="bash other",
            source="polling",
        )
    )
    result = build_session_timeline(store, "Cursor", {100}, expand_tree=False)
    assert len(result) == 1
    assert result[0]["type"] == "shell_exec"
    assert "npm" in result[0]["label"] or "install" in result[0]["label"]


def test_sorted_order_and_label_types() -> None:
    store = EventStore(max_events=100, retention_seconds=120.0)
    pid = 100
    t1, t2, t3, t4 = _ts_offset(90), _ts_offset(85), _ts_offset(80), _ts_offset(75)
    store.push_network(
        NetworkConnectEvent(
            timestamp=t1,
            pid=pid,
            process_name="cursor",
            remote_addr="api.anthropic.com",
            remote_port=443,
            local_port=50000,
            sni="api.anthropic.com",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=t2,
            pid=pid,
            ppid=1,
            name="bash",
            cmdline="bash npm install",
            source="polling",
        )
    )
    store.push_file(
        FileChangeEvent(
            timestamp=t3,
            path="/project/package.json",
            action="modified",
            pid=pid,
            process_name="node",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=t4,
            pid=pid,
            ppid=1,
            name="git",
            cmdline="git commit -m msg",
            source="polling",
        )
    )
    result = build_session_timeline(store, "Cursor", {pid}, expand_tree=False)
    # With sequence boundaries: LLM, sequence_start, shell, file, git, sequence_end
    assert len(result) == 6
    assert result[0]["label"] == "LLM request"
    assert result[0]["type"] == "llm"
    assert result[1]["type"] == "sequence_start"
    assert result[1]["label"] == "[execution sequence]"
    assert result[2]["type"] == "shell_exec"
    assert "npm" in result[2]["label"] or "install" in result[2]["label"]
    assert result[3]["type"] in ("file_write", "file_modified")
    assert "package.json" in result[3]["label"]
    assert result[4]["type"] == "git"
    assert result[4]["label"] == "git commit"
    assert result[5]["type"] == "sequence_end"
    assert result[5]["label"] == "[end sequence]"


def test_file_delete_label() -> None:
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_file(
        FileChangeEvent(
            timestamp=_ts_offset(30),
            path="/tmp/foo.txt",
            action="deleted",
            pid=100,
            source="polling",
        )
    )
    result = build_session_timeline(store, "Tool", {100}, expand_tree=False)
    assert len(result) == 1
    assert result[0]["type"] == "file_delete"
    assert "foo.txt" in result[0]["label"]
    assert "delete" in result[0]["label"].lower()


def test_network_non_llm_label() -> None:
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_network(
        NetworkConnectEvent(
            timestamp=_ts_offset(20),
            pid=100,
            process_name="curl",
            remote_addr="example.com",
            remote_port=443,
            local_port=50001,
            source="polling",
        )
    )
    result = build_session_timeline(store, "Tool", {100}, expand_tree=False)
    assert len(result) == 1
    assert result[0]["type"] == "network"
    assert "connect" in result[0]["label"].lower()
    assert "example" in result[0]["label"].lower()


def test_tree_expansion_includes_child_pids() -> None:
    """When expand_tree=True, events from child PIDs in same tree are included."""
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(60),
            pid=100,
            ppid=1,
            name="Cursor",
            cmdline="Cursor",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(50),
            pid=101,
            ppid=100,
            name="bash",
            cmdline="bash npm install",
            source="polling",
        )
    )
    result = build_session_timeline(store, "Cursor", {100}, expand_tree=True)
    assert len(result) == 2
    labels = [r["label"] for r in result]
    assert any("Cursor" in l for l in labels)
    assert any("npm" in l or "install" in l or "bash" in l for l in labels)


def test_process_attribution_on_entries() -> None:
    """Timeline entries include process_name, pid, parent_pid when available."""
    store = EventStore(max_events=100, retention_seconds=120.0)
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(60),
            pid=100,
            ppid=1,
            name="/usr/bin/cursor",
            cmdline="cursor",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=_ts_offset(50),
            pid=101,
            ppid=100,
            name="bash",
            cmdline="bash npm install",
            source="polling",
        )
    )
    result = build_session_timeline(store, "Cursor", {100, 101}, expand_tree=False)
    assert len(result) >= 2
    # Cursor entry should have pid=100, parent_pid=1; bash should have pid=101, parent_pid=100
    by_pid = {e["pid"]: e for e in result if e.get("pid") is not None}
    assert 100 in by_pid
    assert by_pid[100].get("process_name") == "cursor"
    assert 101 in by_pid
    assert by_pid[101].get("process_name") == "bash"
    assert by_pid[101].get("parent_pid") == 100
    assert by_pid[101].get("parent_process_name") == "cursor"


def test_git_add_and_push_detected() -> None:
    """Git add and push are labeled as type 'git' with short labels."""
    store = EventStore(max_events=100, retention_seconds=120.0)
    pid = 100
    t = _ts_offset(40)
    for cmd, expected_label in (("git add -A", "git add"), ("git push origin main", "git push")):
        store.push_process(
            ProcessExecEvent(timestamp=t, pid=pid, ppid=1, name="git", cmdline=cmd, source="polling")
        )
    result = build_session_timeline(store, "Tool", {pid}, expand_tree=False)
    types = [e["type"] for e in result]
    labels = [e["label"] for e in result]
    assert types.count("git") == 2
    assert "git add" in labels
    assert "git push" in labels


def test_stable_sort_same_timestamp() -> None:
    """Events with identical timestamp keep insertion order (process, then network, then file)."""
    store = EventStore(max_events=100, retention_seconds=120.0)
    pid = 100
    t = _ts_offset(30)
    store.push_process(
        ProcessExecEvent(timestamp=t, pid=pid, ppid=1, name="bash", cmdline="bash first", source="polling")
    )
    store.push_process(
        ProcessExecEvent(timestamp=t, pid=pid, ppid=1, name="bash", cmdline="bash second", source="polling")
    )
    result = build_session_timeline(store, "Tool", {pid}, expand_tree=False)
    assert len(result) == 2
    assert "first" in result[0]["label"]
    assert "second" in result[1]["label"]


def test_timeline_summary_from_entries() -> None:
    """timeline_summary_from_entries counts by type and omits sequence boundaries."""
    entries = [
        {"at": "13:04:02", "label": "LLM request", "type": "llm"},
        {"at": "13:04:02", "label": "[execution sequence]", "type": "sequence_start"},
        {"at": "13:04:05", "label": "bash npm install", "type": "shell_exec"},
        {"at": "13:04:11", "label": "write package.json", "type": "file_write"},
        {"at": "13:04:14", "label": "git commit", "type": "git"},
        {"at": "13:04:14", "label": "[end sequence]", "type": "sequence_end"},
    ]
    summary = timeline_summary_from_entries(entries)
    assert summary.get("llm") == 1
    assert summary.get("shell_exec") == 1
    assert summary.get("file_write") == 1
    assert summary.get("git") == 1
    assert "sequence_start" not in summary
    assert "sequence_end" not in summary
