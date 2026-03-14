"""Mock-based unit tests for the Linux eBPF telemetry provider.

These tests run on any platform by mocking platform checks, BCC imports,
and kernel capabilities.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from telemetry.event_store import EventStore
from providers.ebpf_provider import (
    EBPFProvider,
    _has_capabilities,
    _kernel_ok,
    _parse_kernel_version,
)


# ---- _parse_kernel_version -----------------------------------------------

class TestParseKernelVersion:
    def test_parses_standard_release(self):
        with patch("providers.ebpf_provider.platform.release", return_value="6.1.0-generic"):
            assert _parse_kernel_version() == (6, 1)

    def test_parses_release_with_suffix(self):
        with patch("providers.ebpf_provider.platform.release", return_value="5.15.0-91-generic"):
            assert _parse_kernel_version() == (5, 15)

    def test_parses_simple_version(self):
        with patch("providers.ebpf_provider.platform.release", return_value="4.15.0"):
            assert _parse_kernel_version() == (4, 15)

    def test_returns_none_for_unparseable(self):
        with patch("providers.ebpf_provider.platform.release", return_value="not-a-version"):
            assert _parse_kernel_version() is None

    def test_returns_none_for_single_component(self):
        with patch("providers.ebpf_provider.platform.release", return_value="6"):
            assert _parse_kernel_version() is None


# ---- _kernel_ok -----------------------------------------------------------

class TestKernelOk:
    def test_returns_true_for_5_x(self):
        with patch("providers.ebpf_provider.platform.release", return_value="5.4.0"):
            assert _kernel_ok() is True

    def test_returns_true_for_4_15(self):
        with patch("providers.ebpf_provider.platform.release", return_value="4.15.0"):
            assert _kernel_ok() is True

    def test_returns_false_for_4_14(self):
        with patch("providers.ebpf_provider.platform.release", return_value="4.14.99"):
            assert _kernel_ok() is False

    def test_returns_false_for_3_x(self):
        with patch("providers.ebpf_provider.platform.release", return_value="3.10.0"):
            assert _kernel_ok() is False


# ---- _has_capabilities ----------------------------------------------------

class TestHasCapabilities:
    def test_returns_true_for_root(self):
        with patch("providers.ebpf_provider.os.geteuid", return_value=0):
            assert _has_capabilities() is True

    def test_returns_true_with_both_caps(self):
        cap_bpf = 1 << 39
        cap_perfmon = 1 << 38
        cap_hex = f"CapEff:\t{cap_bpf | cap_perfmon:016x}\n"
        with patch("providers.ebpf_provider.os.geteuid", return_value=1000):
            with patch("builtins.open", mock_open(read_data=f"some line\n{cap_hex}")):
                assert _has_capabilities() is True

    def test_returns_false_without_cap_bpf(self):
        cap_perfmon = 1 << 38
        cap_hex = f"CapEff:\t{cap_perfmon:016x}\n"
        with patch("providers.ebpf_provider.os.geteuid", return_value=1000):
            with patch("builtins.open", mock_open(read_data=f"some line\n{cap_hex}")):
                assert _has_capabilities() is False

    def test_returns_false_without_cap_perfmon(self):
        cap_bpf = 1 << 39
        cap_hex = f"CapEff:\t{cap_bpf:016x}\n"
        with patch("providers.ebpf_provider.os.geteuid", return_value=1000):
            with patch("builtins.open", mock_open(read_data=f"some line\n{cap_hex}")):
                assert _has_capabilities() is False

    def test_returns_false_on_oserror(self):
        with patch("providers.ebpf_provider.os.geteuid", return_value=1000):
            with patch("builtins.open", side_effect=OSError("no such file")):
                assert _has_capabilities() is False


# ---- EBPFProvider.available -----------------------------------------------

class TestEBPFAvailable:
    def test_false_on_non_linux(self):
        with patch("providers.ebpf_provider.sys.platform", "darwin"):
            p = EBPFProvider()
            assert p.available() is False
            assert "Linux" in p.unavailable_reason

    def test_false_when_kernel_too_old(self):
        with patch("providers.ebpf_provider.sys.platform", "linux"):
            with patch("providers.ebpf_provider._kernel_ok", return_value=False):
                p = EBPFProvider()
                assert p.available() is False
                assert "kernel" in p.unavailable_reason or "4.15" in p.unavailable_reason

    def test_false_when_no_capabilities(self):
        with patch("providers.ebpf_provider.sys.platform", "linux"):
            with patch("providers.ebpf_provider._kernel_ok", return_value=True):
                with patch("providers.ebpf_provider._has_capabilities", return_value=False):
                    p = EBPFProvider()
                    assert p.available() is False
                    assert "root" in p.unavailable_reason or "CAP_BPF" in p.unavailable_reason

    def test_false_when_bcc_not_importable(self):
        with patch("providers.ebpf_provider.sys.platform", "linux"):
            with patch("providers.ebpf_provider._kernel_ok", return_value=True):
                with patch("providers.ebpf_provider._has_capabilities", return_value=True):
                    with patch.dict("sys.modules", {"bcc": None}):
                        p = EBPFProvider()
                        assert p.available() is False
                        assert "bcc" in p.unavailable_reason

    def test_true_when_all_conditions_met(self):
        mock_bcc = MagicMock()
        with patch("providers.ebpf_provider.sys.platform", "linux"):
            with patch("providers.ebpf_provider._kernel_ok", return_value=True):
                with patch("providers.ebpf_provider._has_capabilities", return_value=True):
                    with patch.dict("sys.modules", {"bcc": mock_bcc}):
                        p = EBPFProvider()
                        assert p.available() is True

    def test_name_is_ebpf(self):
        assert EBPFProvider().name == "ebpf"


# ---- EBPFProvider.start / stop (mocked BCC) --------------------------------

class TestEBPFLifecycle:
    def _mock_bcc_module(self):
        """Create a mock BCC module with a mock BPF class."""
        mock_bcc = MagicMock()
        mock_bpf_instance = MagicMock()

        mock_bpf_instance.attach_raw_tracepoint = MagicMock()
        mock_bpf_instance.attach_kprobe = MagicMock()
        mock_bpf_instance.attach_kretprobe = MagicMock()
        mock_bpf_instance.get_syscall_fnname = MagicMock(return_value="__x64_sys_openat")
        mock_bpf_instance.perf_buffer_poll = MagicMock()

        mock_perf_buffer = MagicMock()
        mock_bpf_instance.__getitem__ = MagicMock(return_value=mock_perf_buffer)

        mock_bcc.BPF = MagicMock(return_value=mock_bpf_instance)
        return mock_bcc, mock_bpf_instance

    def _mock_ebpf_programs(self):
        """Create mock eBPF program sources."""
        mock_programs = MagicMock()
        mock_programs.EXEC_TRACE_SRC = "/* exec stub */"
        mock_programs.NET_TRACE_SRC = "/* net stub */"
        mock_programs.FILE_TRACE_SRC = "/* file stub */"
        return mock_programs

    def test_start_attaches_all_probes(self):
        mock_bcc, mock_bpf = self._mock_bcc_module()
        mock_programs = self._mock_ebpf_programs()
        store = EventStore()
        provider = EBPFProvider()

        with patch.dict("sys.modules", {
            "bcc": mock_bcc,
            "providers.ebpf_programs": mock_programs,
        }):
            provider.start(store)

        mock_bpf.attach_raw_tracepoint.assert_called_once()
        assert mock_bpf.attach_kprobe.call_count >= 2
        assert mock_bpf.attach_kretprobe.call_count >= 2
        assert provider._store is store
        assert provider._reader_thread is not None

        provider.stop()

    def test_start_survives_partial_attach_failure(self):
        """Provider should still work if some probes fail to attach."""
        mock_bcc, mock_bpf = self._mock_bcc_module()
        mock_programs = self._mock_ebpf_programs()

        mock_bpf.attach_raw_tracepoint.side_effect = Exception("tracepoint failed")

        store = EventStore()
        provider = EBPFProvider()

        with patch.dict("sys.modules", {
            "bcc": mock_bcc,
            "providers.ebpf_programs": mock_programs,
        }):
            provider.start(store)

        assert provider._reader_thread is not None
        provider.stop()

    def test_start_exits_when_all_probes_fail(self):
        """If no probes attach, provider should not start reader thread."""
        mock_bcc, mock_bpf = self._mock_bcc_module()
        mock_programs = self._mock_ebpf_programs()

        mock_bpf.attach_raw_tracepoint.side_effect = Exception("fail")
        mock_bpf.attach_kprobe.side_effect = Exception("fail")
        mock_bpf.get_syscall_fnname.side_effect = Exception("fail")

        store = EventStore()
        provider = EBPFProvider()

        with patch.dict("sys.modules", {
            "bcc": mock_bcc,
            "providers.ebpf_programs": mock_programs,
        }):
            provider.start(store)

        assert provider._reader_thread is None

    def test_start_handles_bpf_load_failure(self):
        """If BPF(text=...) fails, provider should return without crashing."""
        mock_bcc = MagicMock()
        mock_bcc.BPF.side_effect = Exception("compilation failed")
        mock_programs = self._mock_ebpf_programs()

        store = EventStore()
        provider = EBPFProvider()

        with patch.dict("sys.modules", {
            "bcc": mock_bcc,
            "providers.ebpf_programs": mock_programs,
        }):
            provider.start(store)

        assert provider._bpf is None
        assert provider._reader_thread is None

    def test_stop_cleans_up_state(self):
        provider = EBPFProvider()
        provider._bpf = MagicMock()
        provider._store = MagicMock()
        provider._stop_event = threading.Event()
        provider._reader_thread = MagicMock()

        provider.stop()

        assert provider._bpf is None
        assert provider._store is None
        assert provider._stop_event is None

    def test_stop_without_start_is_safe(self):
        provider = EBPFProvider()
        provider.stop()

    def test_reader_thread_polls_perf_buffer(self):
        """Verify the reader loop calls perf_buffer_poll."""
        mock_bcc, mock_bpf = self._mock_bcc_module()
        mock_programs = self._mock_ebpf_programs()

        call_count = 0
        original_poll = mock_bpf.perf_buffer_poll

        def counting_poll(timeout_ms=100):
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                provider._stop_event.set()

        mock_bpf.perf_buffer_poll = counting_poll

        store = EventStore()
        provider = EBPFProvider()

        with patch.dict("sys.modules", {
            "bcc": mock_bcc,
            "providers.ebpf_programs": mock_programs,
        }):
            provider.start(store)

        provider._reader_thread.join(timeout=3.0)
        assert call_count >= 3
        provider.stop()
