"""Tests for the PollingProvider."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from telemetry.event_store import EventStore
from providers.polling import PollingProvider


def test_available_returns_true() -> None:
    provider = PollingProvider()
    assert provider.available() is True


def test_name_is_polling() -> None:
    provider = PollingProvider()
    assert provider.name == "polling"


def test_poll_produces_process_events() -> None:
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)

    mock_proc = MagicMock()
    mock_proc.info = {
        "pid": 12345,
        "name": "python",
        "cmdline": ["python", "main.py"],
        "username": "testuser",
        "ppid": 1000,
    }

    with patch("providers.polling.psutil.process_iter") as mock_iter:
        mock_iter.return_value = [mock_proc]
        with patch("providers.polling.psutil.net_connections") as mock_net:
            mock_net.return_value = []
            provider.poll()

    events = store.get_process_events()
    assert len(events) >= 1
    proc_events = [e for e in events if e.pid == 12345]
    assert len(proc_events) == 1
    assert proc_events[0].name == "python"
    assert proc_events[0].source == "polling"


def test_poll_produces_network_events() -> None:
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)

    mock_conn = MagicMock()
    mock_conn.pid = 999
    mock_conn.laddr = MagicMock()
    mock_conn.laddr.port = 54321
    mock_conn.raddr = MagicMock()
    mock_conn.raddr.ip = "192.168.1.1"
    mock_conn.raddr.port = 443

    with patch("providers.polling.psutil.process_iter") as mock_iter:
        mock_iter.return_value = []
        with patch("providers.polling.psutil.net_connections") as mock_net:
            mock_net.return_value = [mock_conn]
            with patch("providers.polling.psutil.Process") as mock_process:
                mock_process.return_value.name.return_value = "curl"
                provider.poll()

    events = store.get_network_events()
    assert len(events) >= 1
    net_events = [e for e in events if e.pid == 999]
    assert len(net_events) == 1
    assert net_events[0].remote_addr == "192.168.1.1"
    assert net_events[0].source == "polling"


def test_poll_events_have_source_polling() -> None:
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)

    with patch("providers.polling.psutil.process_iter") as mock_iter:
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 1,
            "name": "init",
            "cmdline": ["/sbin/init"],
            "username": "root",
            "ppid": 0,
        }
        mock_iter.return_value = [mock_proc]
        with patch("providers.polling.psutil.net_connections") as mock_net:
            mock_net.return_value = []
            provider.poll()

    events = store.get_process_events()
    assert all(e.source == "polling" for e in events)


def test_poll_handles_psutil_exceptions() -> None:
    import psutil

    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)

    with patch("providers.polling.psutil.process_iter") as mock_iter:
        mock_iter.side_effect = psutil.AccessDenied()
        with patch("providers.polling.psutil.net_connections") as mock_net:
            mock_net.return_value = []
            provider.poll()

    events = store.get_process_events()
    assert len(events) == 0


def test_poll_does_nothing_when_store_not_started() -> None:
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.poll()
    assert len(store.get_process_events()) == 0
    assert len(store.get_network_events()) == 0


def test_stop_clears_store_reference() -> None:
    store = EventStore(max_events=1000, retention_seconds=60.0)
    provider = PollingProvider()
    provider.start(store)
    provider.stop()
    provider.poll()
    assert len(store.get_process_events()) == 0


def test_registry_native_raises() -> None:
    from providers import get_best_provider
    from providers import registry

    with patch.object(registry, "_try_native", return_value=None):
        with pytest.raises(RuntimeError, match="No native telemetry provider"):
            get_best_provider("native")


def test_registry_auto_returns_polling() -> None:
    from providers import get_best_provider
    from providers import registry

    with patch.object(registry, "_try_native", return_value=None):
        provider = get_best_provider("auto")
        assert provider.name == "polling"


def test_registry_polling_returns_polling() -> None:
    from providers import get_best_provider

    provider = get_best_provider("polling")
    assert provider.name == "polling"
