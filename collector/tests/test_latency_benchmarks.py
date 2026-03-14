"""Latency and throughput benchmarks for EventStore."""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from telemetry.event_store import EventStore, ProcessExecEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_event(pid: int = 1) -> ProcessExecEvent:
    return ProcessExecEvent(
        timestamp=_utc_now(),
        pid=pid,
        ppid=0,
        name="claude",
        cmdline="claude",
        source="polling",
    )


@pytest.mark.benchmark
@pytest.mark.slow
def test_push_to_alert_callback_under_1ms() -> None:
    callback_times: list[float] = []

    def on_alert(event: ProcessExecEvent) -> None:
        callback_times.append(time.perf_counter())

    store = EventStore(max_events=10_000, retention_seconds=60.0, on_alert=on_alert)
    t0 = time.perf_counter()
    store.push_process(_make_event())
    t1 = time.perf_counter()
    elapsed = (t1 - t0) * 1000
    assert elapsed < 1.0, f"push_process took {elapsed:.3f}ms, target < 1ms"
    if callback_times:
        callback_delta = (callback_times[0] - t0) * 1000
        assert callback_delta < 1.0, f"callback fired {callback_delta:.3f}ms after push, target < 1ms"


@pytest.mark.benchmark
@pytest.mark.slow
def test_throughput_10000_events_under_1_second() -> None:
    store = EventStore(max_events=20_000, retention_seconds=60.0)
    t0 = time.perf_counter()
    for i in range(10_000):
        store.push_process(_make_event(pid=i))
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"10,000 pushes took {elapsed:.3f}s, target < 1s"
    events = store.get_process_events()
    assert len(events) == 10_000


@pytest.mark.benchmark
@pytest.mark.slow
def test_get_process_events_10000_completes_under_100ms() -> None:
    store = EventStore(max_events=20_000, retention_seconds=60.0)
    for i in range(10_000):
        store.push_process(_make_event(pid=i))
    t0 = time.perf_counter()
    events = store.get_process_events()
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 100.0, f"get_process_events took {elapsed:.1f}ms, target < 100ms"
    assert len(events) == 10_000
