"""Mock-based unit tests for the macOS ESF telemetry provider.

These tests run on any platform by mocking platform checks, the esf_helper
subprocess, and the Unix domain socket communication.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from telemetry.event_store import EventStore


def _recent_ts() -> str:
    """Timestamp within retention window so get_*_events() does not evict."""
    return (datetime.now(timezone.utc) - timedelta(seconds=60)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# Helper: make ESFProvider importable on non-macOS by patching sys.platform
# at module-load time is not needed because the module imports fine everywhere.
# ---------------------------------------------------------------------------

from providers.esf_provider import (
    ESF_SOURCE,
    ESFProvider,
    _find_esf_helper,
    _macos_version_ok,
)


# ---- _macos_version_ok ---------------------------------------------------


class TestMacOSVersionOk:
    def test_returns_false_on_linux(self):
        with patch("providers.esf_provider.sys.platform", "linux"):
            assert _macos_version_ok() is False

    def test_returns_false_on_catalina_predecessor(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch(
                "providers.esf_provider.platform.mac_ver",
                return_value=("10.14.6", ("", "", ""), ""),
            ):
                assert _macos_version_ok() is False

    def test_returns_true_on_catalina(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch(
                "providers.esf_provider.platform.mac_ver",
                return_value=("10.15.0", ("", "", ""), ""),
            ):
                assert _macos_version_ok() is True

    def test_returns_true_on_ventura(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch(
                "providers.esf_provider.platform.mac_ver",
                return_value=("13.0.0", ("", "", ""), ""),
            ):
                assert _macos_version_ok() is True

    def test_returns_true_on_sonoma(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch(
                "providers.esf_provider.platform.mac_ver",
                return_value=("14.2.1", ("", "", ""), ""),
            ):
                assert _macos_version_ok() is True

    def test_returns_false_on_empty_version(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch(
                "providers.esf_provider.platform.mac_ver",
                return_value=("", ("", "", ""), ""),
            ):
                assert _macos_version_ok() is False


# ---- _find_esf_helper ----------------------------------------------------


class TestFindESFHelper:
    def test_finds_helper_on_path(self):
        with patch(
            "providers.esf_provider.shutil.which",
            return_value="/usr/local/bin/esf_helper",
        ):
            with patch("providers.esf_provider.os.access", return_value=True):
                with patch("providers.esf_provider.Path.is_file", return_value=False):
                    result = _find_esf_helper()
                    assert result == "/usr/local/bin/esf_helper"

    def test_returns_none_when_not_found(self):
        with patch("providers.esf_provider.shutil.which", return_value=None):
            with patch("providers.esf_provider.Path.is_file", return_value=False):
                with patch("providers.esf_provider.os.access", return_value=False):
                    result = _find_esf_helper()
                    assert result is None


# ---- ESFProvider.available ------------------------------------------------


class TestESFAvailable:
    def test_false_on_non_darwin(self):
        with patch("providers.esf_provider.sys.platform", "linux"):
            p = ESFProvider()
            assert p.available() is False
            assert "macOS" in p.unavailable_reason

    def test_false_when_version_too_old(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch("providers.esf_provider._macos_version_ok", return_value=False):
                p = ESFProvider()
                assert p.available() is False
                assert "10.15" in p.unavailable_reason

    def test_false_when_helper_missing(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch("providers.esf_provider._macos_version_ok", return_value=True):
                with patch(
                    "providers.esf_provider._find_esf_helper", return_value=None
                ):
                    p = ESFProvider()
                    assert p.available() is False
                    assert "helper" in p.unavailable_reason.lower()

    def test_true_when_all_conditions_met(self):
        with patch("providers.esf_provider.sys.platform", "darwin"):
            with patch("providers.esf_provider._macos_version_ok", return_value=True):
                with patch(
                    "providers.esf_provider._find_esf_helper",
                    return_value="/usr/bin/esf_helper",
                ):
                    with patch("providers.esf_provider.os.access", return_value=True):
                        p = ESFProvider()
                        assert p.available() is True
                        assert p.unavailable_reason == ""


# ---- ESFProvider._process_line (JSON event parsing) -----------------------


class TestESFProcessLine:
    """Test the _process_line method that parses JSON from esf_helper."""

    def _make_provider_with_store(self) -> tuple[ESFProvider, EventStore]:
        store = EventStore(max_events=1000, retention_seconds=86400.0)
        provider = ESFProvider()
        provider._store = store
        return provider, store

    def test_exec_event_parsed(self):
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "exec",
                "pid": 1234,
                "ppid": 100,
                "name": "claude",
                "cmdline": "claude chat --model opus",
                "username": "dev",
                "binary_path": "/usr/local/bin/claude",
                "timestamp": _recent_ts(),
            }
        )
        provider._process_line(line)

        events = store.get_process_events()
        assert len(events) == 1, "expected one process event"
        ev = events[0]
        assert ev.pid == 1234
        assert ev.ppid == 100
        assert ev.name == "claude"
        assert ev.cmdline == "claude chat --model opus"
        assert ev.binary_path == "/usr/local/bin/claude"
        assert ev.source == ESF_SOURCE

    def test_open_event_readonly_parsed_as_file_read(self):
        """Read-only open (flags=0) is pushed as FileReadEvent, not FileChangeEvent."""
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "open",
                "path": "/etc/hosts",
                "flags": 0,
                "pid": 42,
                "process_name": "cat",
                "timestamp": _recent_ts(),
            }
        )
        provider._process_line(line)
        provider._flush_read_batch()

        read_events = store.get_file_read_events()
        assert len(read_events) == 1
        ev = read_events[0]
        assert ev.path == "/etc/hosts"
        assert ev.pid == 42
        assert ev.source == ESF_SOURCE
        assert len(store.get_file_events()) == 0

    def test_open_event_writable_parsed_as_modified(self):
        """Writable open is pushed as FileChangeEvent (use path not filtered as temp)."""
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "open",
                "path": "/etc/output.log",
                "flags": 0x3,
                "pid": 99,
                "process_name": "python",
                "timestamp": _recent_ts(),
            }
        )
        provider._process_line(line)
        provider._flush_file_batch()

        events = store.get_file_events()
        assert len(events) == 1
        assert events[0].action == "modified"

    def test_uipc_connect_event_parsed(self):
        """uipc_connect events (Unix-domain IPC) are emitted with protocol=unix."""
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "uipc_connect",
                "pid": 555,
                "process_name": "claude",
                "socket_path": "/tmp/claude.sock",
                "sock_type": "stream",
                "timestamp": _recent_ts(),
            }
        )
        provider._process_line(line)

        events = store.get_network_events()
        assert len(events) == 1
        ev = events[0]
        assert ev.pid == 555
        assert ev.process_name == "claude"
        assert ev.remote_addr == "/tmp/claude.sock"
        assert ev.protocol == "unix"
        assert ev.source == ESF_SOURCE

    def test_legacy_connect_event_ignored(self):
        """The old 'connect' event type is no longer emitted by esf_helper.
        ESF does not expose TCP connect events; psutil handles TCP enumeration.
        Legacy 'connect' lines should be silently ignored (no crash)."""
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "connect",
                "pid": 555,
                "process_name": "curl",
                "remote_addr": "10.0.0.1",
                "remote_port": 443,
                "protocol": "tcp",
                "timestamp": _recent_ts(),
            }
        )
        provider._process_line(line)
        # No events should be emitted — this type is no longer handled.
        assert len(store.get_network_events()) == 0

    def test_malformed_json_is_ignored(self):
        provider, store = self._make_provider_with_store()
        provider._process_line("not valid json {{{")
        assert len(store.get_process_events()) == 0
        assert len(store.get_network_events()) == 0
        assert len(store.get_file_events()) == 0
        assert len(store.get_file_read_events()) == 0

    def test_unknown_event_type_is_ignored(self):
        provider, store = self._make_provider_with_store()
        line = json.dumps({"type": "unknown_type", "data": "hello"})
        provider._process_line(line)
        assert len(store.get_process_events()) == 0
        assert len(store.get_file_read_events()) == 0

    def test_missing_type_field_is_ignored(self):
        provider, store = self._make_provider_with_store()
        line = json.dumps({"pid": 1, "name": "test"})
        provider._process_line(line)
        assert len(store.get_process_events()) == 0

    def test_bad_timestamp_uses_utc_now(self):
        provider, store = self._make_provider_with_store()
        line = json.dumps(
            {
                "type": "exec",
                "pid": 1,
                "ppid": 0,
                "name": "test",
                "cmdline": "test",
                "timestamp": "not-a-timestamp",
            }
        )
        provider._process_line(line)
        events = store.get_process_events()
        assert len(events) == 1
        assert events[0].timestamp.tzinfo is not None


# ---- ESFProvider.start / stop lifecycle -----------------------------------


class TestESFLifecycle:
    @pytest.mark.skipif(
        not getattr(socket, "AF_UNIX", None),
        reason="AF_UNIX not available on this platform",
    )
    def test_start_launches_helper_and_connects_socket(self):
        store = EventStore()
        provider = ESFProvider()

        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_proc.returncode = None

        mock_socket = MagicMock()

        with patch(
            "providers.esf_provider._find_esf_helper",
            return_value="/usr/bin/esf_helper",
        ):
            with patch(
                "providers.esf_provider.subprocess.Popen", return_value=mock_proc
            ) as mock_popen:
                with patch("providers.esf_provider.os.path.exists", return_value=True):
                    with patch(
                        "providers.esf_provider.socket.socket", return_value=mock_socket
                    ):
                        with patch(
                            "providers.esf_provider.tempfile.mkstemp",
                            return_value=(5, "/tmp/detec-esf-test.sock"),
                        ):
                            with patch("providers.esf_provider.os.close"):
                                with patch("providers.esf_provider.os.unlink"):
                                    provider.start(store)

        mock_popen.assert_called_once()
        mock_socket.connect.assert_called_once_with("/tmp/detec-esf-test.sock")
        assert provider._store is store
        assert provider._reader_thread is not None

        provider._stop_event.set()
        provider.stop()

    def test_start_raises_when_helper_not_found(self):
        store = EventStore()
        provider = ESFProvider()

        with patch("providers.esf_provider._find_esf_helper", return_value=None):
            with pytest.raises(RuntimeError, match="esf_helper not found"):
                provider.start(store)

    def test_stop_terminates_helper(self):
        provider = ESFProvider()
        provider._proc = MagicMock()
        provider._proc.wait.return_value = 0
        provider._sock = MagicMock()
        provider._sock_path = "/tmp/test.sock"
        provider._reader_thread = MagicMock()
        provider._stop_event = threading.Event()
        provider._store = MagicMock()

        provider.stop()

        provider._proc is None  # cleared by _cleanup
        assert provider._store is None

    def test_name_is_esf(self):
        assert ESFProvider().name == "esf"
