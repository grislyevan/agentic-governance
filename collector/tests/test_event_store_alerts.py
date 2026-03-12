"""Tests for EventStore on_alert callback mechanism."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from telemetry.event_store import EventStore, ProcessExecEvent


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _make_event(
    name: str,
    cmdline: str | None = None,
    pid: int = 1,
    ppid: int = 0,
) -> ProcessExecEvent:
    return ProcessExecEvent(
        timestamp=_utc_now(),
        pid=pid,
        ppid=ppid,
        name=name,
        cmdline=cmdline or name,
        source="polling",
    )


def test_alert_fires_for_agentic_pattern_in_name() -> None:
    alerts: list[ProcessExecEvent] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    store.push_process(_make_event("claude"))
    store.push_process(_make_event("cursor-helper"))
    store.push_process(_make_event("ollama serve", cmdline="ollama serve"))

    assert len(alerts) == 3
    assert alerts[0].name == "claude"
    assert alerts[1].name == "cursor-helper"
    assert alerts[2].name == "ollama serve"


def test_alert_does_not_fire_for_non_matching_events() -> None:
    alerts: list[ProcessExecEvent] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    store.push_process(_make_event("firefox"))
    store.push_process(_make_event("python3"))
    store.push_process(_make_event("nginx"))

    assert len(alerts) == 0


def test_alert_fires_for_shell_fanout() -> None:
    alerts: list[ProcessExecEvent] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    ppid = 1000
    for i, shell in enumerate(["bash", "zsh", "sh", "fish", "dash"]):
        store.push_process(
            _make_event(shell, cmdline=shell, pid=2000 + i, ppid=ppid)
        )

    assert len(alerts) >= 1
    assert any(e.name in ("bash", "zsh", "sh", "fish", "dash") for e in alerts)


def test_alert_does_not_fire_below_shell_threshold() -> None:
    alerts: list[ProcessExecEvent] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    ppid = 2000
    for i, shell in enumerate(["bash", "zsh", "sh", "fish"]):
        store.push_process(
            _make_event(shell, cmdline=shell, pid=3000 + i, ppid=ppid)
        )

    assert len(alerts) == 0


def test_concurrent_pushes_no_errors() -> None:
    alerts: list[ProcessExecEvent] = []
    errors: list[Exception] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=50_000, retention_seconds=60.0, on_alert=on_alert)

    def push_agentic(start: int, count: int) -> None:
        try:
            for i in range(start, start + count):
                store.push_process(
                    _make_event("cursor", pid=i, ppid=0)
                )
        except Exception as e:
            errors.append(e)

    threads = [
        Thread(target=push_agentic, args=(i * 1000, 500))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(alerts) >= 1


def test_no_error_when_on_alert_is_none() -> None:
    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=None)
    store.push_process(_make_event("claude"))
    store.push_process(_make_event("cursor"))
    events = store.get_process_events()
    assert len(events) == 2


def test_callback_exception_caught_and_logged() -> None:
    def on_alert(event: ProcessExecEvent) -> None:
        raise ValueError("callback error")

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    store.push_process(_make_event("claude"))
    events = store.get_process_events()
    assert len(events) == 1


def test_alert_fires_for_cmdline_match_when_name_does_not_match() -> None:
    alerts: list[ProcessExecEvent] = []

    def on_alert(event: ProcessExecEvent) -> None:
        alerts.append(event)

    store = EventStore(max_events=100, retention_seconds=60.0, on_alert=on_alert)
    store.push_process(
        _make_event("python3", cmdline="python3 -m aider")
    )

    assert len(alerts) == 1
    assert "aider" in alerts[0].cmdline
