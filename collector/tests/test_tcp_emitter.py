"""Tests for collector.output.tcp_emitter: TcpEmitter unit tests.

These tests validate the emitter's interface, queue management, and
buffer fallback without requiring a live server.
"""

from __future__ import annotations

import queue
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from collector.output.tcp_emitter import TcpEmitter, _QueueItem, _BATCH_SIZE


class TestTcpEmitterInterface:
    """Verify the emitter exposes the same interface as HttpEmitter."""

    def _make_emitter(self) -> TcpEmitter:
        return TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
        )

    def test_has_emit(self) -> None:
        e = self._make_emitter()
        assert callable(e.emit)

    def test_has_heartbeat(self) -> None:
        e = self._make_emitter()
        assert callable(e.heartbeat)

    def test_has_flush_buffer(self) -> None:
        e = self._make_emitter()
        assert callable(e.flush_buffer)

    def test_has_stats(self) -> None:
        e = self._make_emitter()
        s = e.stats
        assert "sent" in s
        assert "buffered" in s
        assert "buffer_size" in s
        assert "emitted" in s
        assert "failed" in s

    def test_stats_initial_values(self) -> None:
        e = self._make_emitter()
        s = e.stats
        assert s["sent"] == 0
        assert s["buffered"] == 0


class TestQueueItem:
    def test_event_item(self) -> None:
        item = _QueueItem("event", {"event_id": "ev-1"})
        assert item.kind == "event"
        assert item.data["event_id"] == "ev-1"

    def test_heartbeat_item(self) -> None:
        item = _QueueItem("heartbeat", {"hostname": "h1"})
        assert item.kind == "heartbeat"


class TestEmitQueuing:
    """Test that emit() places events on the send queue."""

    def test_emit_enqueues_event(self) -> None:
        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
        )
        # Prevent the background thread from starting a connection
        e._started = True

        ev = {"event_id": str(uuid.uuid4()), "event_type": "tool.detected"}
        result = e.emit(ev)
        assert result is True
        assert e._send_queue.qsize() == 1

        item = e._send_queue.get_nowait()
        assert item.kind == "event"
        assert item.data["event_id"] == ev["event_id"]

    def test_heartbeat_enqueues(self) -> None:
        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
        )
        e._started = True

        result = e.heartbeat("myhost", interval_seconds=300)
        assert result is True

        item = e._send_queue.get_nowait()
        assert item.kind == "heartbeat"
        assert item.data["hostname"] == "myhost"


class TestBufferFallback:
    """Test that the emitter falls back to local buffer when queue is full."""

    def test_full_queue_buffers_event(self) -> None:
        mock_buffer = MagicMock()
        mock_buffer.size.return_value = 0

        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
            buffer=mock_buffer,
        )
        e._started = True
        # Make queue very small so it fills up
        e._send_queue = queue.Queue(maxsize=1)
        e._send_queue.put(_QueueItem("event", {}))

        ev = {"event_id": "overflow"}
        result = e.emit(ev)
        assert result is False
        mock_buffer.append.assert_called_once_with(ev)
        assert e._buffered == 1

    def test_spill_queue_to_buffer(self) -> None:
        mock_buffer = MagicMock()
        mock_buffer.size.return_value = 0
        mock_buffer.drain.return_value = []

        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
            buffer=mock_buffer,
        )
        e._started = True

        for i in range(3):
            e._send_queue.put(_QueueItem("event", {"event_id": f"ev-{i}"}))
        e._send_queue.put(_QueueItem("heartbeat", {}))

        e._spill_queue_to_buffer()

        assert mock_buffer.append.call_count == 3
        assert e._buffered == 3

    def test_flush_buffer_requeues(self) -> None:
        mock_buffer = MagicMock()
        mock_buffer.drain.return_value = [
            {"event_id": "buf-1"},
            {"event_id": "buf-2"},
        ]
        mock_buffer.size.return_value = 0

        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
            buffer=mock_buffer,
        )
        e._started = True

        flushed = e.flush_buffer()
        assert flushed == 2
        assert e._send_queue.qsize() == 2


class TestCallbacks:
    def test_on_command_callback_stored(self) -> None:
        cb = MagicMock()
        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
            on_command=cb,
        )
        assert e._on_command is cb

    def test_on_policy_callback_stored(self) -> None:
        cb = MagicMock()
        e = TcpEmitter(
            gateway_host="127.0.0.1",
            gateway_port=19999,
            api_key="test-key",
            hostname="test-host",
            on_policy=cb,
        )
        assert e._on_policy is cb
