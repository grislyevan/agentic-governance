"""Tests for protocol.connection: BaseConnection frame I/O and lifecycle."""

from __future__ import annotations

import asyncio
import struct

import pytest

from protocol.connection import BaseConnection
from protocol.wire import MessageType, encode_frame, HEADER_SIZE
from protocol.messages import heartbeat_msg, auth_msg, ack_msg


class EchoConnection(BaseConnection):
    """Test subclass that records received messages."""

    def __init__(self, reader, writer, **kwargs):
        super().__init__(reader, writer, **kwargs)
        self.received: list[dict] = []

    async def handle_message(self, msg):
        self.received.append(msg)


def _make_stream_pair() -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Create an in-memory StreamReader and a mock StreamWriter for testing."""
    reader = asyncio.StreamReader()
    transport = _MockTransport()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport.set_protocol(protocol)
    protocol.connection_made(transport)
    writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())
    return reader, writer


class _MockTransport(asyncio.Transport):
    """Minimal transport that captures writes and supports wait_closed."""

    def __init__(self):
        super().__init__()
        self.data = bytearray()
        self._closing = False
        self._extra: dict = {}
        self._protocol: asyncio.BaseProtocol | None = None

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    def is_closing(self) -> bool:
        return self._closing

    def close(self) -> None:
        self._closing = True
        if self._protocol and hasattr(self._protocol, "connection_lost"):
            self._protocol.connection_lost(None)

    def get_extra_info(self, name, default=None):
        return self._extra.get(name, default)

    def set_protocol(self, protocol: asyncio.BaseProtocol) -> None:
        self._protocol = protocol

    def get_protocol(self) -> asyncio.BaseProtocol | None:
        return self._protocol


pytestmark = pytest.mark.asyncio


class TestBaseConnectionSend:
    @pytest.mark.asyncio
    async def test_send_writes_framed_data(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")

        msg = heartbeat_msg(seq=1)
        await conn.send(msg)

        transport: _MockTransport = writer.transport  # type: ignore[assignment]
        raw = bytes(transport.data)

        assert len(raw) > HEADER_SIZE
        payload_len = struct.unpack("!I", raw[:HEADER_SIZE])[0]
        assert payload_len == len(raw) - HEADER_SIZE

    @pytest.mark.asyncio
    async def test_send_after_close_raises(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")
        await conn.close()

        with pytest.raises(ConnectionError):
            await conn.send(heartbeat_msg())


class TestBaseConnectionRecv:
    @pytest.mark.asyncio
    async def test_recv_decodes_frame(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")

        frame = encode_frame(auth_msg("key", "host", "1.0", seq=5))
        reader.feed_data(frame)

        msg = await conn.recv()
        assert msg is not None
        assert msg["t"] == MessageType.AUTH
        assert msg["id"] == 5

    @pytest.mark.asyncio
    async def test_recv_returns_none_on_eof(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")
        reader.feed_eof()

        msg = await conn.recv()
        assert msg is None


class TestBaseConnectionRun:
    @pytest.mark.asyncio
    async def test_run_processes_messages_then_closes(self) -> None:
        reader, writer = _make_stream_pair()
        conn = EchoConnection(reader, writer, label="test", keepalive_interval=999)

        frame1 = encode_frame(heartbeat_msg(seq=1))
        frame2 = encode_frame(ack_msg([1, 2], seq=2))
        reader.feed_data(frame1 + frame2)
        reader.feed_eof()

        await conn.run()

        assert len(conn.received) == 2
        assert conn.received[0]["t"] == MessageType.HEARTBEAT
        assert conn.received[1]["t"] == MessageType.ACK
        assert conn.closed


class TestNextSeq:
    @pytest.mark.asyncio
    async def test_increments(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")
        assert conn.next_seq() == 1
        assert conn.next_seq() == 2
        assert conn.next_seq() == 3


class TestClose:
    @pytest.mark.asyncio
    async def test_idempotent(self) -> None:
        reader, writer = _make_stream_pair()
        conn = BaseConnection(reader, writer, label="test")
        await conn.close()
        await conn.close()
        assert conn.closed
