"""Wire format: framing, message types, encode/decode.

Each message on the wire is length-prefixed:

    [4 bytes: payload length (big-endian uint32)] [N bytes: msgpack payload]

The msgpack payload is a map with keys: t (type), id (sequence), ts (timestamp), p (payload).
"""

from __future__ import annotations

import enum
import struct
import time
from typing import Any

import msgpack

HEADER_SIZE = 4
MAX_FRAME_SIZE = 16 * 1024 * 1024  # 16 MiB safety limit


class MessageType(enum.IntEnum):
    """Wire message type codes."""

    AUTH = 0x01
    AUTH_OK = 0x02
    AUTH_FAIL = 0x03

    EVENT = 0x10
    EVENT_BATCH = 0x11
    ACK = 0x12
    NACK = 0x13

    HEARTBEAT = 0x20
    HEARTBEAT_ACK = 0x21

    POLICY_PUSH = 0x30
    COMMAND = 0x31
    COMMAND_ACK = 0x32
    POSTURE_PUSH = 0x33

    ERROR = 0xFF


def encode_frame(msg: dict[str, Any]) -> bytes:
    """Encode a message dict into a length-prefixed msgpack frame.

    The message must contain at least 't' (message type). If 'ts' is missing,
    the current time is used. 'id' defaults to 0.
    """
    if "t" not in msg:
        raise ValueError("Message must contain 't' (message type)")

    envelope: dict[str, Any] = {
        "t": int(msg["t"]),
        "id": msg.get("id", 0),
        "ts": msg.get("ts", time.time()),
        "p": msg.get("p", {}),
    }

    payload = msgpack.packb(envelope, use_bin_type=True)
    if len(payload) > MAX_FRAME_SIZE:
        raise ValueError(f"Frame payload exceeds {MAX_FRAME_SIZE} bytes ({len(payload)})")
    return struct.pack("!I", len(payload)) + payload


def decode_frame(data: bytes) -> dict[str, Any]:
    """Decode a raw msgpack payload (without the length prefix) into a message dict."""
    msg = msgpack.unpackb(data, raw=False)
    if not isinstance(msg, dict):
        raise ValueError(f"Expected msgpack map, got {type(msg).__name__}")
    if "t" not in msg:
        raise ValueError("Decoded message missing 't' (message type)")
    return msg


class FrameReader:
    """Incremental frame reader that buffers incoming bytes.

    Feed chunks via ``feed(data)`` and retrieve complete messages from
    ``messages()``. This is useful for both threaded (socket.recv) and
    async (StreamReader) transports.
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> None:
        """Append raw bytes from the transport."""
        self._buf.extend(data)

    def messages(self) -> list[dict[str, Any]]:
        """Extract all complete frames from the buffer.

        Returns a list of decoded message dicts. Partial frames stay
        in the internal buffer for the next ``feed()`` call.
        """
        result: list[dict[str, Any]] = []
        while len(self._buf) >= HEADER_SIZE:
            payload_len = struct.unpack("!I", self._buf[:HEADER_SIZE])[0]
            if payload_len > MAX_FRAME_SIZE:
                raise ValueError(f"Frame size {payload_len} exceeds limit {MAX_FRAME_SIZE}")
            total = HEADER_SIZE + payload_len
            if len(self._buf) < total:
                break
            payload = bytes(self._buf[HEADER_SIZE:total])
            del self._buf[:total]
            result.append(decode_frame(payload))
        return result

    def reset(self) -> None:
        """Clear the internal buffer."""
        self._buf.clear()


async def async_read_frame(reader: Any) -> dict[str, Any] | None:
    """Read a single length-prefixed frame from an asyncio StreamReader.

    Returns None on EOF.
    """
    header = await reader.readexactly(HEADER_SIZE)
    if len(header) < HEADER_SIZE:
        return None
    payload_len = struct.unpack("!I", header)[0]
    if payload_len > MAX_FRAME_SIZE:
        raise ValueError(f"Frame size {payload_len} exceeds limit {MAX_FRAME_SIZE}")
    payload = await reader.readexactly(payload_len)
    return decode_frame(payload)
