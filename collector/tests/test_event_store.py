"""Tests for the EventStore ring buffer."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Thread

import pytest

from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def test_push_and_query_process_events() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_process(
        ProcessExecEvent(
            timestamp=now,
            pid=123,
            ppid=1,
            name="python",
            cmdline="python main.py",
            source="polling",
        )
    )
    events = store.get_process_events()
    assert len(events) == 1
    assert events[0].pid == 123
    assert events[0].name == "python"


def test_push_and_query_network_events() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=456,
            process_name="curl",
            remote_addr="1.2.3.4",
            remote_port=443,
            local_port=54321,
            source="polling",
        )
    )
    events = store.get_network_events()
    assert len(events) == 1
    assert events[0].pid == 456
    assert events[0].remote_addr == "1.2.3.4"


def test_push_and_query_file_events() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_file(
        FileChangeEvent(
            timestamp=now,
            path="/tmp/foo.txt",
            action="modified",
            source="polling",
        )
    )
    events = store.get_file_events()
    assert len(events) == 1
    assert events[0].path == "/tmp/foo.txt"
    assert events[0].action == "modified"


def test_process_name_pattern_filter() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_process(
        ProcessExecEvent(
            timestamp=now,
            pid=1,
            ppid=0,
            name="claude",
            cmdline="claude",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=now,
            pid=2,
            ppid=0,
            name="bash",
            cmdline="bash",
            source="polling",
        )
    )
    events = store.get_process_events(name_pattern=r"claude")
    assert len(events) == 1
    assert events[0].name == "claude"


def test_network_pid_filter() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=100,
            process_name="a",
            remote_addr="x",
            remote_port=80,
            local_port=1,
            source="polling",
        )
    )
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=200,
            process_name="b",
            remote_addr="y",
            remote_port=80,
            local_port=2,
            source="polling",
        )
    )
    events = store.get_network_events(pid=100)
    assert len(events) == 1
    assert events[0].pid == 100


def test_network_remote_addr_filter() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=1,
            process_name="a",
            remote_addr="api.example.com",
            remote_port=443,
            local_port=1,
            source="polling",
        )
    )
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=2,
            process_name="b",
            remote_addr="other.com",
            remote_port=443,
            local_port=2,
            source="polling",
        )
    )
    events = store.get_network_events(remote_addr="api.example.com")
    assert len(events) == 1
    assert events[0].remote_addr == "api.example.com"


def test_file_path_prefix_filter() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_file(
        FileChangeEvent(
            timestamp=now,
            path="/home/user/.config/tool/config.json",
            action="modified",
            source="polling",
        )
    )
    store.push_file(
        FileChangeEvent(
            timestamp=now,
            path="/tmp/other.txt",
            action="created",
            source="polling",
        )
    )
    events = store.get_file_events(path_prefix="/home/user/.config")
    assert len(events) == 1
    assert events[0].path.startswith("/home/user/.config")


def test_since_filter() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    base = _utc_now()
    store.push_process(
        ProcessExecEvent(
            timestamp=base,
            pid=1,
            ppid=0,
            name="old",
            cmdline="old",
            source="polling",
        )
    )
    store.push_process(
        ProcessExecEvent(
            timestamp=base + timedelta(seconds=10),
            pid=2,
            ppid=0,
            name="new",
            cmdline="new",
            source="polling",
        )
    )
    since = base + timedelta(seconds=5)
    events = store.get_process_events(since=since)
    assert len(events) == 1
    assert events[0].name == "new"


def test_retention_eviction() -> None:
    store = EventStore(max_events=100, retention_seconds=0.1)
    old_time = _utc_now() - timedelta(seconds=60)
    store.push_process(
        ProcessExecEvent(
            timestamp=old_time,
            pid=1,
            ppid=0,
            name="old",
            cmdline="old",
            source="polling",
        )
    )
    events = store.get_process_events()
    assert len(events) == 0


def test_ring_buffer_overflow() -> None:
    store = EventStore(max_events=3, retention_seconds=3600.0)
    now = _utc_now()
    for i in range(5):
        store.push_process(
            ProcessExecEvent(
                timestamp=now,
                pid=i,
                ppid=0,
                name=f"p{i}",
                cmdline="",
                source="polling",
            )
        )
    events = store.get_process_events()
    assert len(events) == 3
    pids = {e.pid for e in events}
    assert pids == {2, 3, 4}


def test_thread_safety() -> None:
    store = EventStore(max_events=50_000, retention_seconds=60.0)
    errors: list[Exception] = []

    def push_processes(start: int, count: int) -> None:
        try:
            now = _utc_now()
            for i in range(start, start + count):
                store.push_process(
                    ProcessExecEvent(
                        timestamp=now,
                        pid=i,
                        ppid=0,
                        name=f"p{i}",
                        cmdline="",
                        source="polling",
                    )
                )
        except Exception as e:
            errors.append(e)

    threads = [
        Thread(target=push_processes, args=(i * 1000, 1000))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    events = store.get_process_events()
    assert len(events) == 10_000


def test_has_event_driven_source_false_when_only_polling() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_process(
        ProcessExecEvent(
            timestamp=now,
            pid=1,
            ppid=0,
            name="x",
            cmdline="x",
            source="polling",
        )
    )
    assert store.has_event_driven_source() is False


def test_has_event_driven_source_true_when_non_polling() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_process(
        ProcessExecEvent(
            timestamp=now,
            pid=1,
            ppid=0,
            name="x",
            cmdline="x",
            source="esf",
        )
    )
    assert store.has_event_driven_source() is True


def test_has_event_driven_source_true_from_network() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_network(
        NetworkConnectEvent(
            timestamp=now,
            pid=1,
            process_name="x",
            remote_addr="a",
            remote_port=80,
            local_port=1,
            source="etw",
        )
    )
    assert store.has_event_driven_source() is True


def test_has_event_driven_source_true_from_file() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0)
    now = _utc_now()
    store.push_file(
        FileChangeEvent(
            timestamp=now,
            path="/tmp/x",
            action="created",
            source="ebpf",
        )
    )
    assert store.has_event_driven_source() is True
