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

from engine.session_timeline import build_session_timeline


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
    assert len(result) == 4
    assert result[0]["label"] == "LLM request"
    assert result[0]["type"] == "llm"
    assert result[1]["type"] == "shell_exec"
    assert "npm" in result[1]["label"] or "install" in result[1]["label"]
    assert result[2]["type"] in ("file_write", "file_modified")
    assert "package.json" in result[2]["label"]
    assert result[3]["type"] == "exec"
    assert "git" in result[3]["label"].lower()


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
