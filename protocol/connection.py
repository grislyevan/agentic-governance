"""BaseConnection: TLS/TCP connection with frame read/write and keepalive.

Subclassed by the server-side ``AgentSession`` and the agent-side
``TcpEmitter``.  Handles:

- TLS wrapping (optional, for non-TLS dev/test)
- Length-prefixed msgpack frame I/O
- Periodic keepalive (heartbeat exchange)
- Clean shutdown with drain
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import struct
import time
from typing import Any, Callable, Coroutine

from protocol.wire import (
    HEADER_SIZE,
    MAX_FRAME_SIZE,
    MessageType,
    encode_frame,
    decode_frame,
)

logger = logging.getLogger(__name__)

DEFAULT_KEEPALIVE_INTERVAL = 30  # seconds
DEFAULT_KEEPALIVE_TIMEOUT = 10  # seconds


class BaseConnection:
    """Async connection wrapper around an asyncio StreamReader/StreamWriter pair.

    Provides framed read/write and keepalive. Subclasses implement
    ``handle_message()`` for application-level dispatch.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        keepalive_interval: int = DEFAULT_KEEPALIVE_INTERVAL,
        keepalive_timeout: int = DEFAULT_KEEPALIVE_TIMEOUT,
        label: str = "connection",
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._keepalive_interval = keepalive_interval
        self._keepalive_timeout = keepalive_timeout
        self._label = label

        self._closed = False
        self._last_recv: float = time.monotonic()
        self._last_send: float = time.monotonic()
        self._seq: int = 0
        self._read_task: asyncio.Task[None] | None = None
        self._keepalive_task: asyncio.Task[None] | None = None

    @property
    def closed(self) -> bool:
        return self._closed

    def next_seq(self) -> int:
        """Return the next sequence number for outbound messages."""
        self._seq += 1
        return self._seq

    # -- Frame I/O -----------------------------------------------------------

    async def send(self, msg: dict[str, Any]) -> None:
        """Encode and send a single message."""
        if self._closed:
            raise ConnectionError(f"{self._label}: connection closed")
        frame = encode_frame(msg)
        self._writer.write(frame)
        await self._writer.drain()
        self._last_send = time.monotonic()

    async def recv(self) -> dict[str, Any] | None:
        """Read a single length-prefixed frame. Returns None on EOF."""
        try:
            header = await self._reader.readexactly(HEADER_SIZE)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None

        payload_len = struct.unpack("!I", header)[0]
        if payload_len > MAX_FRAME_SIZE:
            raise ValueError(f"Frame size {payload_len} exceeds limit")

        try:
            payload = await self._reader.readexactly(payload_len)
        except (asyncio.IncompleteReadError, ConnectionError):
            return None

        self._last_recv = time.monotonic()
        return decode_frame(payload)

    # -- Read loop -----------------------------------------------------------

    async def run(self) -> None:
        """Start the read loop and keepalive. Blocks until the connection closes."""
        self._read_task = asyncio.current_task()
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        try:
            await self._read_loop()
        finally:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass
            await self.close()

    async def _read_loop(self) -> None:
        while not self._closed:
            msg = await self.recv()
            if msg is None:
                logger.info("%s: remote end closed", self._label)
                break
            try:
                await self.handle_message(msg)
            except Exception:
                logger.exception("%s: error handling message type 0x%02x", self._label, msg.get("t", 0))

    async def handle_message(self, msg: dict[str, Any]) -> None:
        """Process a received message. Override in subclasses."""
        logger.debug("%s: unhandled message type 0x%02x", self._label, msg.get("t", 0))

    # -- Keepalive -----------------------------------------------------------

    async def _keepalive_loop(self) -> None:
        """Send heartbeat if idle for ``keepalive_interval`` seconds."""
        while not self._closed:
            await asyncio.sleep(self._keepalive_interval)
            idle = time.monotonic() - self._last_send
            if idle >= self._keepalive_interval:
                try:
                    from protocol.messages import heartbeat_msg
                    await self.send(heartbeat_msg(seq=self.next_seq()))
                except ConnectionError:
                    break

    # -- Shutdown ------------------------------------------------------------

    async def close(self) -> None:
        """Close the transport gracefully."""
        if self._closed:
            return
        self._closed = True
        try:
            if not self._writer.is_closing():
                self._writer.close()
            try:
                await asyncio.wait_for(self._writer.wait_closed(), timeout=5.0)
            except (asyncio.TimeoutError, NotImplementedError):
                pass
        except Exception:
            logger.debug("%s: error during close", self._label, exc_info=True)

    # -- TLS helpers ---------------------------------------------------------

    @staticmethod
    def make_server_ssl_context(
        certfile: str,
        keyfile: str,
        *,
        cafile: str | None = None,
    ) -> ssl.SSLContext:
        """Build a TLS context for the server side."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        if cafile:
            ctx.load_verify_locations(cafile)
            ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    @staticmethod
    def make_client_ssl_context(
        *,
        cafile: str | None = None,
        verify: bool = True,
    ) -> ssl.SSLContext:
        """Build a TLS context for the agent (client) side."""
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if cafile:
            ctx.load_verify_locations(cafile)
        if not verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx
