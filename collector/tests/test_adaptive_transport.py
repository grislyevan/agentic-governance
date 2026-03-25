"""Tests for adaptive transport (protocol auto) and config aliases.

Server-side deduplication by event_id (HTTP and TCP ingest) is covered in
api/tests/test_events.py::test_ingest_duplicate_is_idempotent.
"""

from __future__ import annotations

import json
import time
import unittest
from unittest.mock import MagicMock, patch


class TestTryTcpAuth(unittest.TestCase):
    def test_try_tcp_auth_connection_refused(self) -> None:
        from output.tcp_emitter import try_tcp_auth

        ok, reason = try_tcp_auth(
            "127.0.0.1",
            59999,
            "k",
            "h",
            "1.0.0",
            tls=False,
            timeout=0.5,
        )
        self.assertFalse(ok)
        self.assertTrue(reason)

class TestAdaptiveEmitter(unittest.TestCase):
    @patch("output.adaptive_emitter.try_tcp_auth")
    def test_auto_falls_back_to_http_when_tcp_fails(self, mock_try: MagicMock) -> None:
        from output.adaptive_emitter import AdaptiveEmitter

        mock_try.return_value = (False, "connection refused")
        ae = AdaptiveEmitter(
            api_url="http://localhost:8000/api",
            api_key="key",
            hostname="testhost",
            agent_version="1.0.0",
            gateway_host="localhost",
            gateway_port=8001,
            tls=False,
            tcp_connect_timeout=0.1,
            tcp_retry_interval=3600.0,
            tcp_failure_threshold=5,
            tcp_recovery_stability=1.0,
            sign_events=False,
        )
        self.assertTrue(ae.uses_http_heartbeat())
        ev = {
            "event_id": "00000000-0000-4000-8000-000000000001",
            "event_type": "tool.detected",
            "event_version": "1.0.0",
            "observed_at": "2025-01-01T00:00:00+00:00",
        }
        with patch.object(ae._http, "emit", return_value=True) as m:
            ae.emit(ev)
            m.assert_called_once_with(ev)
        ae.shutdown()

    @patch("output.adaptive_emitter.try_tcp_auth")
    def test_auto_uses_tcp_when_probe_succeeds(self, mock_try: MagicMock) -> None:
        from output.adaptive_emitter import AdaptiveEmitter

        mock_try.return_value = (True, "")
        ae = AdaptiveEmitter(
            api_url="https://example.com/api",
            api_key="key",
            hostname="testhost",
            agent_version="1.0.0",
            gateway_host="example.com",
            gateway_port=8001,
            tls=True,
            tcp_connect_timeout=0.1,
            tcp_retry_interval=3600.0,
            tcp_failure_threshold=99,
            tcp_recovery_stability=1.0,
            sign_events=False,
        )
        self.assertFalse(ae.uses_http_heartbeat())
        assert ae._tcp is not None
        with patch.object(ae._tcp, "emit", return_value=True) as m:
            ev = {
                "event_id": "00000000-0000-4000-8000-000000000002",
                "event_type": "tool.detected",
                "event_version": "1.0.0",
                "observed_at": "2025-01-01T00:00:00+00:00",
            }
            ae.emit(ev)
            m.assert_called_once_with(ev)
        ae.shutdown()

    @patch("output.adaptive_emitter.try_tcp_auth")
    def test_recovery_switches_back_to_tcp(self, mock_try: MagicMock) -> None:
        from output.adaptive_emitter import AdaptiveEmitter

        mock_try.return_value = (False, "nope")
        ae = AdaptiveEmitter(
            api_url="http://localhost:8000/api",
            api_key="key",
            hostname="h",
            agent_version="1.0.0",
            gateway_host="localhost",
            gateway_port=8001,
            tls=False,
            tcp_connect_timeout=0.1,
            tcp_retry_interval=0.15,
            tcp_failure_threshold=5,
            tcp_recovery_stability=0.05,
            sign_events=False,
        )
        self.assertTrue(ae.uses_http_heartbeat())
        mock_try.return_value = (True, "")
        time.sleep(0.35)
        for _ in range(50):
            if not ae.uses_http_heartbeat():
                break
            time.sleep(0.05)
        self.assertFalse(ae.uses_http_heartbeat(), "expected TCP recovery")
        ae.shutdown()


class TestTcpHostAlias(unittest.TestCase):
    def test_tcp_host_maps_to_gateway_host(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        from config_loader import load_collector_config

        with TemporaryDirectory() as td:
            p = Path(td) / "collector.json"
            p.write_text(
                json.dumps(
                    {
                        "api_url": "http://x/api",
                        "api_key": "k",
                        "protocol": "auto",
                        "tcp_host": "gw.example.com",
                        "tcp_port": 9001,
                    }
                )
            )
            cfg = load_collector_config(p)
            self.assertEqual(cfg["gateway_host"], "gw.example.com")
            self.assertEqual(cfg["gateway_port"], 9001)


class TestTcpEmitterFailover(unittest.TestCase):
    def test_no_failover_when_threshold_none(self) -> None:
        from output.tcp_emitter import TcpEmitter

        te = TcpEmitter(
            "127.0.0.1",
            59998,
            "k",
            "h",
            "1.0.0",
            failover_threshold=None,
            on_degraded=None,
        )
        self.assertFalse(te._should_failover(100, 0.0))

    def test_consecutive_failures_triggers_failover(self) -> None:
        """Exactly N consecutive failures (failover_threshold=N) triggers failover;
        N-1 does not. disconnect_since=0.0 ensures elapsed >> 1.0 so the time
        guard does not interfere."""
        from output.tcp_emitter import TcpEmitter

        degraded_called: list[bool] = []

        te = TcpEmitter(
            "127.0.0.1",
            59998,
            "k",
            "h",
            "1.0.0",
            failover_threshold=3,
            on_degraded=lambda: degraded_called.append(True),
        )

        # N-1 failures should NOT trigger failover
        self.assertFalse(te._should_failover(2, 0.0))
        # Exactly N failures SHOULD trigger failover
        self.assertTrue(te._should_failover(3, 0.0))
        # More than N should also trigger
        self.assertTrue(te._should_failover(10, 0.0))

    def test_failover_requires_elapsed_time(self) -> None:
        """Failover is not triggered if disconnect_since is None (no disconnect yet)."""
        from output.tcp_emitter import TcpEmitter

        te = TcpEmitter(
            "127.0.0.1",
            59998,
            "k",
            "h",
            "1.0.0",
            failover_threshold=1,
            on_degraded=lambda: None,
        )
        # disconnect_since=None means _should_failover returns False regardless
        self.assertFalse(te._should_failover(100, None))

    def test_http_fallback_sends_events(self) -> None:
        """When TCP auth fails at startup, events must be delivered via the HTTP
        emitter, not dropped."""
        from output.adaptive_emitter import AdaptiveEmitter

        with patch("output.adaptive_emitter.try_tcp_auth") as mock_try:
            mock_try.return_value = (False, "connection refused")
            ae = AdaptiveEmitter(
                api_url="http://localhost:8000/api",
                api_key="key",
                hostname="testhost",
                agent_version="1.0.0",
                gateway_host="localhost",
                gateway_port=8001,
                tls=False,
                tcp_connect_timeout=0.1,
                tcp_retry_interval=3600.0,
                tcp_failure_threshold=5,
                tcp_recovery_stability=1.0,
                sign_events=False,
            )
            self.assertTrue(ae.uses_http_heartbeat(), "expected HTTP fallback after TCP auth failure")

            ev = {
                "event_id": "00000000-0000-4000-8000-000000000099",
                "event_type": "tool.detected",
                "event_version": "1.0.0",
                "observed_at": "2026-01-01T00:00:00+00:00",
            }
            with patch.object(ae._http, "emit", return_value=True) as mock_emit:
                result = ae.emit(ev)
                # Event should have been sent via HTTP emitter
                mock_emit.assert_called_once_with(ev)
                self.assertTrue(result)
            ae.shutdown()

    def test_failover_resets_on_reconnect(self) -> None:
        """After HTTP fallback, a subsequent successful TCP auth probe re-enables
        the TCP path (recovery_worker switches back). Uses short retry interval
        so the test does not block long."""
        from output.adaptive_emitter import AdaptiveEmitter

        with patch("output.adaptive_emitter.try_tcp_auth") as mock_try:
            # First call: TCP unavailable → HTTP fallback
            mock_try.return_value = (False, "nope")
            ae = AdaptiveEmitter(
                api_url="http://localhost:8000/api",
                api_key="key",
                hostname="h",
                agent_version="1.0.0",
                gateway_host="localhost",
                gateway_port=8001,
                tls=False,
                tcp_connect_timeout=0.1,
                tcp_retry_interval=0.15,
                tcp_failure_threshold=5,
                tcp_recovery_stability=0.05,
                sign_events=False,
            )
            self.assertTrue(ae.uses_http_heartbeat(), "should be in HTTP fallback initially")

            # Simulate TCP recovery: next probes succeed
            mock_try.return_value = (True, "")
            # Wait for recovery worker to detect the successful probe
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if not ae.uses_http_heartbeat():
                    break
                time.sleep(0.05)
            self.assertFalse(ae.uses_http_heartbeat(), "expected TCP path restored after recovery probes succeeded")
            ae.shutdown()
