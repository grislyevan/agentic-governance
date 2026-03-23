"""Mock-based unit tests for the Windows ETW telemetry provider.

These tests run on any platform by mocking platform checks, admin detection,
and the pywintrace / ctypes ETW APIs.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from telemetry.event_store import EventStore
from providers.etw_provider import (
    ETWProvider,
    _is_admin,
    _check_ctypes_etw,
    _check_pywintrace,
    _parse_event_pywintrace,
    _SOURCE,
)


# ---- Platform / admin checks ---------------------------------------------

class TestPlatformChecks:
    def test_is_admin_returns_false_on_non_windows(self):
        with patch("providers.etw_provider.sys.platform", "darwin"):
            assert _is_admin() is False

    def test_check_ctypes_etw_returns_false_on_non_windows(self):
        with patch("providers.etw_provider.sys.platform", "linux"):
            assert _check_ctypes_etw() is False

    def test_check_pywintrace_returns_false_when_not_installed(self):
        with patch.dict("sys.modules", {"etw": None}):
            assert _check_pywintrace() is False


# ---- ETWProvider.available ------------------------------------------------

class TestETWAvailable:
    def test_false_on_non_windows(self):
        with patch("providers.etw_provider.sys.platform", "linux"):
            p = ETWProvider()
            assert p.available() is False
            assert "Windows" in p.unavailable_reason

    def test_false_when_not_admin(self):
        with patch("providers.etw_provider.sys.platform", "win32"):
            with patch("providers.etw_provider._is_admin", return_value=False):
                p = ETWProvider()
                assert p.available() is False
                assert "admin" in p.unavailable_reason.lower() or "Administrator" in p.unavailable_reason

    def test_true_with_pywintrace(self):
        with patch("providers.etw_provider.sys.platform", "win32"):
            with patch("providers.etw_provider._is_admin", return_value=True):
                with patch("providers.etw_provider._check_pywintrace", return_value=True):
                    p = ETWProvider()
                    assert p.available() is True
                    assert p.unavailable_reason == ""

    def test_true_with_ctypes_fallback(self):
        with patch("providers.etw_provider.sys.platform", "win32"):
            with patch("providers.etw_provider._is_admin", return_value=True):
                with patch("providers.etw_provider._check_pywintrace", return_value=False):
                    with patch("providers.etw_provider._check_ctypes_etw", return_value=True):
                        p = ETWProvider()
                        assert p.available() is True

    def test_false_when_no_backend_available(self):
        with patch("providers.etw_provider.sys.platform", "win32"):
            with patch("providers.etw_provider._is_admin", return_value=True):
                with patch("providers.etw_provider._check_pywintrace", return_value=False):
                    with patch("providers.etw_provider._check_ctypes_etw", return_value=False):
                        p = ETWProvider()
                        assert p.available() is False
                        assert "pywintrace" in p.unavailable_reason.lower() or "ctypes" in p.unavailable_reason.lower()

    def test_name_is_etw(self):
        assert ETWProvider().name == "etw"


# ---- _parse_event_pywintrace (process events) ----------------------------

class TestParseProcessEvents:
    def test_parses_process_creation_event(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "ProcessId": 4567,
            "ParentId": 1000,
            "ImageFileName": "claude.exe",
            "CommandLine": "claude.exe chat --model opus",
        }
        _parse_event_pywintrace(store, (1, event_dict))

        events = store.get_process_events()
        assert len(events) == 1
        ev = events[0]
        assert ev.pid == 4567
        assert ev.ppid == 1000
        assert ev.name == "claude.exe"
        assert ev.cmdline == "claude.exe chat --model opus"
        assert ev.source == _SOURCE

    def test_handles_missing_optional_fields(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "ProcessId": 100,
            "ParentId": 1,
        }
        _parse_event_pywintrace(store, (1, event_dict))

        events = store.get_process_events()
        assert len(events) == 1
        assert events[0].name == "unknown"
        assert events[0].cmdline == ""

    def test_process_event_has_utc_timestamp(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {"ProcessId": 1, "ParentId": 0}
        _parse_event_pywintrace(store, (1, event_dict))

        events = store.get_process_events()
        assert events[0].timestamp.tzinfo is not None


# ---- _parse_event_pywintrace (network events) ----------------------------

class TestParseNetworkEvents:
    def test_parses_network_event_with_daddr(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "daddr": "10.0.0.1",
            "dport": 443,
            "sport": 54321,
            "PID": 2222,
            "ProcessName": "curl",
        }
        _parse_event_pywintrace(store, (10, event_dict))

        events = store.get_network_events()
        assert len(events) == 1
        ev = events[0]
        assert ev.remote_addr == "10.0.0.1"
        assert ev.remote_port == 443
        assert ev.local_port == 54321
        assert ev.pid == 2222
        assert ev.process_name == "curl"
        assert ev.source == _SOURCE

    def test_parses_network_event_with_RemoteAddr(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "RemoteAddr": "192.168.1.50",
            "RemotePort": 8080,
            "LocalPort": 12345,
            "ProcessId": 333,
        }
        _parse_event_pywintrace(store, (10, event_dict))

        events = store.get_network_events()
        assert len(events) == 1
        assert events[0].remote_addr == "192.168.1.50"

    def test_handles_bytes_daddr(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "daddr": b"172.16.0.1",
            "dport": 80,
            "PID": 10,
        }
        _parse_event_pywintrace(store, (10, event_dict))

        events = store.get_network_events()
        assert len(events) == 1
        assert events[0].remote_addr == "172.16.0.1"


# ---- _parse_event_pywintrace (file events) -------------------------------

class TestParseFileEvents:
    def test_parses_file_create_event(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "FileName": "C:\\Users\\dev\\document.txt",
            "PID": 4000,
            "ProcessName": "notepad.exe",
        }
        _parse_event_pywintrace(store, (12, event_dict))

        events = store.get_file_events()
        assert len(events) == 1
        ev = events[0]
        assert ev.path == "C:\\Users\\dev\\document.txt"
        assert ev.action == "created"  # event_id == 12 => created
        assert ev.source == _SOURCE

    def test_parses_file_modify_event(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "FileName": "C:\\temp\\output.log",
            "PID": 5000,
        }
        _parse_event_pywintrace(store, (15, event_dict))

        events = store.get_file_events()
        assert len(events) == 1
        assert events[0].action == "modified"  # event_id != 12 => modified

    def test_ignores_file_event_without_path(self):
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {"FileObject": ""}
        _parse_event_pywintrace(store, (12, event_dict))

        assert len(store.get_file_events()) == 0


# ---- ETWProvider.start / stop (pywintrace backend) -----------------------

class TestETWLifecycle:
    def test_start_with_pywintrace(self):
        mock_etw_module = MagicMock()
        mock_etw_instance = MagicMock()
        mock_etw_module.ETW.return_value = mock_etw_instance
        mock_etw_module.ProviderInfo = MagicMock()
        mock_etw_module.GUID = MagicMock()

        store = EventStore()
        provider = ETWProvider()

        with patch.dict("sys.modules", {"etw": mock_etw_module}):
            with patch("providers.etw_provider._check_pywintrace", return_value=True):
                provider.start(store)

        mock_etw_module.ETW.assert_called_once()
        mock_etw_instance.start.assert_called_once()
        assert provider._store is store

    def test_stop_calls_etw_stop(self):
        provider = ETWProvider()
        mock_etw = MagicMock()
        provider._etw = mock_etw
        provider._store = MagicMock()

        provider.stop()

        mock_etw.stop.assert_called_once()
        assert provider._store is None
        assert provider._etw is None

    def test_stop_handles_exception_in_etw_stop(self):
        provider = ETWProvider()
        mock_etw = MagicMock()
        mock_etw.stop.side_effect = RuntimeError("cleanup error")
        provider._etw = mock_etw
        provider._store = MagicMock()

        provider.stop()
        assert provider._etw is None

    def test_stop_without_start_is_safe(self):
        provider = ETWProvider()
        provider.stop()


# ---- Disambiguation: events with overlapping keys -------------------------

class TestEventDisambiguation:
    def test_process_event_takes_priority_over_network(self):
        """When ProcessId and ParentId are present, it's a process event."""
        store = EventStore(max_events=500, retention_seconds=60.0)
        event_dict = {
            "ProcessId": 123,
            "ParentId": 1,
            "ImageFileName": "test.exe",
            "daddr": "10.0.0.1",  # also has network fields
        }
        _parse_event_pywintrace(store, (1, event_dict))

        assert len(store.get_process_events()) == 1
        assert len(store.get_network_events()) == 0
