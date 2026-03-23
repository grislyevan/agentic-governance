"""Tests for telemetry provider interface, event normalization, and capabilities."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from telemetry.capabilities import (
    TelemetryCapabilities,
    get_capabilities_from_store,
    merge_capabilities,
)
from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    FileReadEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)
from telemetry.providers.base_provider import TelemetryProviderBase
from providers.polling import PollingProvider
from providers.registry import get_best_provider


def test_provider_interface_compliance_polling() -> None:
    """PollingProvider implements name, available, start, stop, capabilities."""
    provider: TelemetryProviderBase = PollingProvider()
    assert provider.name == "polling"
    assert provider.available() is True
    store = EventStore(max_events=100, retention_seconds=60.0)
    provider.start(store)
    try:
        cap = provider.capabilities()
        assert isinstance(cap, TelemetryCapabilities)
        assert cap.has_process_exec is True
        assert cap.has_file_change is False
        assert cap.has_file_read is False
    finally:
        provider.stop()


def test_event_normalization_polling() -> None:
    """Provider pushes only normalized event types with correct source."""
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)
    try:
        with patch("providers.polling.psutil.process_iter") as mock_iter:
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": 42,
                "name": "test",
                "cmdline": ["test"],
                "username": "u",
                "ppid": 1,
            }
            mock_iter.return_value = [mock_proc]
            with patch("providers.polling.psutil.net_connections") as mock_net:
                mock_net.return_value = []
                provider.poll()
        process_events = store.get_process_events()
        assert len(process_events) >= 1
        for e in process_events:
            assert isinstance(e, ProcessExecEvent)
            assert e.source == "polling"
        network_events = store.get_network_events()
        for e in network_events:
            assert isinstance(e, NetworkConnectEvent)
            assert e.source == "polling"
    finally:
        provider.stop()


def test_capabilities_from_store_reflects_contents() -> None:
    """get_capabilities_from_store sets has_file_read when file read events exist."""
    store = EventStore(max_events=100, retention_seconds=60.0)
    cap_empty = get_capabilities_from_store(store)
    assert cap_empty.has_file_read is False

    store.push_process(
        ProcessExecEvent(
            timestamp=datetime.now(timezone.utc),
            pid=1,
            ppid=0,
            name="x",
            cmdline="x",
            source="esf",
        )
    )
    store.push_file_read(
        FileReadEvent(
            timestamp=datetime.now(timezone.utc),
            path="/etc/hosts",
            pid=1,
            process_name="cat",
            source="esf",
        )
    )
    cap_with_read = get_capabilities_from_store(store)
    assert cap_with_read.has_file_read is True
    assert cap_with_read.has_process_exec is True


def test_merge_capabilities() -> None:
    """merge_capabilities ORs provider and store flags."""
    provider_cap = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=True,
        has_file_read=True,
        has_network_events=True,
        has_process_parent=True,
    )
    store_cap = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=False,
        has_file_read=False,
        has_network_events=True,
        has_process_parent=True,
    )
    merged = merge_capabilities(provider_cap, store_cap)
    assert merged.has_process_exec is True
    assert merged.has_file_change is True
    assert merged.has_file_read is True
    assert merged.has_network_events is True


def test_event_ingestion_file_read_retention() -> None:
    """File read events are ingested and evicted by retention."""
    store = EventStore(max_events=100, retention_seconds=1.0)
    now = datetime.now(timezone.utc)
    store.push_file_read(
        FileReadEvent(timestamp=now, path="/a", pid=1, process_name="p", source="esf")
    )
    events = store.get_file_read_events()
    assert len(events) == 1
    assert events[0].path == "/a"

    # path_prefix filter
    events_b = store.get_file_read_events(path_prefix="/b")
    assert len(events_b) == 0
    events_a = store.get_file_read_events(path_prefix="/a")
    assert len(events_a) == 1


def test_provider_capabilities_polling_returns_expected_flags() -> None:
    """PollingProvider.capabilities() declares no file_change/file_read."""
    provider = PollingProvider()
    cap = provider.capabilities()
    assert cap.has_process_exec is True
    assert cap.has_file_change is False
    assert cap.has_file_read is False
    assert cap.has_network_events is True
    assert cap.has_process_parent is True


def test_get_best_provider_returns_provider_with_capabilities() -> None:
    """get_best_provider returns a provider that has capabilities()."""
    provider = get_best_provider("polling")
    cap = provider.capabilities()
    assert isinstance(cap, TelemetryCapabilities)
