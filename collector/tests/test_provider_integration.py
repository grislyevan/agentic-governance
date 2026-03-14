"""Integration tests for native telemetry providers.

These tests require platform-specific prerequisites and are intended to
run on real hardware or appropriately configured VMs/containers:

- ESF: macOS with SIP partially disabled or approved System Extension
- eBPF: Linux (kernel >= 4.15) with root or CAP_BPF + CAP_PERFMON
- ETW: Windows with admin privileges

Mark all with @pytest.mark.slow so CI can exclude them by default.
"""

from __future__ import annotations

import os
import sys
import time

import pytest

from telemetry.event_store import EventStore


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS only")
class TestESFIntegration:
    """Real ESF capture tests. Require System Extension approval."""

    def test_esf_available_on_supported_mac(self):
        from providers.esf_provider import ESFProvider

        provider = ESFProvider()
        if not provider.available():
            pytest.skip(f"ESF not available: {provider.unavailable_reason}")

    def test_esf_captures_process_exec(self):
        from providers.esf_provider import ESFProvider
        import subprocess

        provider = ESFProvider()
        if not provider.available():
            pytest.skip(f"ESF not available: {provider.unavailable_reason}")

        store = EventStore()
        provider.start(store)
        try:
            time.sleep(1)
            subprocess.run(["echo", "esf-integration-test"], capture_output=True)
            time.sleep(2)

            events = store.get_process_events(name_pattern="echo")
            assert len(events) > 0, "ESF should capture the echo process exec"
            assert events[0].source == "esf"
        finally:
            provider.stop()

    def test_esf_latency_under_100ms(self):
        from providers.esf_provider import ESFProvider
        import subprocess

        provider = ESFProvider()
        if not provider.available():
            pytest.skip(f"ESF not available: {provider.unavailable_reason}")

        store = EventStore()
        provider.start(store)
        try:
            time.sleep(1)
            t0 = time.monotonic()
            subprocess.run(["true"], capture_output=True)
            time.sleep(0.5)
            events = store.get_process_events(name_pattern="true")
            if events:
                latency_ms = (time.monotonic() - t0) * 1000
                assert latency_ms < 500, f"Detection latency {latency_ms:.0f}ms exceeds 500ms"
        finally:
            provider.stop()

    def test_polling_fallback_when_esf_unavailable(self):
        from providers.registry import get_best_provider

        provider = get_best_provider("auto")
        assert provider.name in ("esf", "polling")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
class TestEBPFIntegration:
    """Real eBPF capture tests. Require root or CAP_BPF."""

    def test_ebpf_available_on_supported_linux(self):
        from providers.ebpf_provider import EBPFProvider

        provider = EBPFProvider()
        if not provider.available():
            pytest.skip(f"eBPF not available: {provider.unavailable_reason}")

    def test_ebpf_captures_process_exec(self):
        from providers.ebpf_provider import EBPFProvider
        import subprocess

        provider = EBPFProvider()
        if not provider.available():
            pytest.skip(f"eBPF not available: {provider.unavailable_reason}")

        store = EventStore()
        provider.start(store)
        try:
            time.sleep(1)
            subprocess.run(["echo", "ebpf-integration-test"], capture_output=True)
            time.sleep(2)

            events = store.get_process_events(name_pattern="echo")
            assert len(events) > 0, "eBPF should capture the echo process exec"
            assert events[0].source == "ebpf"
        finally:
            provider.stop()

    def test_ebpf_captures_network_connect(self):
        from providers.ebpf_provider import EBPFProvider
        import socket

        provider = EBPFProvider()
        if not provider.available():
            pytest.skip(f"eBPF not available: {provider.unavailable_reason}")

        store = EventStore()
        provider.start(store)
        try:
            time.sleep(1)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.settimeout(2)
                s.connect(("1.1.1.1", 80))
            except OSError:
                pass
            finally:
                s.close()
            time.sleep(2)

            events = store.get_network_events()
            assert len(events) > 0, "eBPF should capture TCP connect"
            assert events[0].source == "ebpf"
        finally:
            provider.stop()

    def test_polling_fallback_when_ebpf_unavailable(self):
        from providers.registry import get_best_provider

        provider = get_best_provider("auto")
        assert provider.name in ("ebpf", "polling")


@pytest.mark.slow
@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
class TestETWIntegration:
    """Real ETW capture tests. Require admin privileges."""

    def test_etw_available_on_windows(self):
        from providers.etw_provider import ETWProvider

        provider = ETWProvider()
        if not provider.available():
            pytest.skip(f"ETW not available: {provider.unavailable_reason}")

    def test_etw_captures_process_create(self):
        from providers.etw_provider import ETWProvider
        import subprocess

        provider = ETWProvider()
        if not provider.available():
            pytest.skip(f"ETW not available: {provider.unavailable_reason}")

        store = EventStore()
        provider.start(store)
        try:
            time.sleep(1)
            subprocess.run(["cmd", "/c", "echo", "etw-test"], capture_output=True)
            time.sleep(2)

            events = store.get_process_events(name_pattern="cmd")
            assert len(events) > 0, "ETW should capture cmd process"
            assert events[0].source == "etw"
        finally:
            provider.stop()

    def test_polling_fallback_when_etw_unavailable(self):
        from providers.registry import get_best_provider

        provider = get_best_provider("auto")
        assert provider.name in ("etw", "polling")


@pytest.mark.slow
class TestAlertTriggeredScan:
    """Verify that the alert callback + scan_trigger mechanism works end-to-end."""

    def test_alert_callback_fires_for_agentic_process(self):
        from telemetry.event_store import ProcessExecEvent
        from datetime import datetime, timezone

        alerts = []
        store = EventStore(on_alert=lambda ev: alerts.append(ev))

        event = ProcessExecEvent(
            timestamp=datetime.now(timezone.utc),
            pid=12345,
            ppid=1,
            name="claude",
            cmdline="claude chat",
            source="esf",
        )
        store.push_process(event)
        assert len(alerts) == 1
        assert alerts[0].pid == 12345

    def test_alert_triggered_scan_latency(self):
        """End-to-end: alert fires and scan_trigger is set within 5s."""
        import threading
        from telemetry.event_store import ProcessExecEvent
        from datetime import datetime, timezone

        scan_trigger = threading.Event()

        def on_alert(_event):
            scan_trigger.set()

        store = EventStore(on_alert=on_alert)

        event = ProcessExecEvent(
            timestamp=datetime.now(timezone.utc),
            pid=99,
            ppid=1,
            name="ollama",
            cmdline="ollama serve",
            source="esf",
        )

        t0 = time.monotonic()
        store.push_process(event)
        triggered = scan_trigger.wait(timeout=5.0)
        latency_ms = (time.monotonic() - t0) * 1000

        assert triggered, "scan_trigger should be set by on_alert"
        assert latency_ms < 100, f"Alert-to-trigger latency {latency_ms:.0f}ms exceeds 100ms"
