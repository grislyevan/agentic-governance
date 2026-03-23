"""Tests for protocol.wire: framing, encode/decode, FrameReader."""

from __future__ import annotations

import struct
import time

import msgpack
import pytest

from protocol.wire import (
    HEADER_SIZE,
    MAX_FRAME_SIZE,
    MessageType,
    FrameReader,
    decode_frame,
    encode_frame,
)


class TestMessageType:
    def test_all_codes_are_unique(self) -> None:
        values = [m.value for m in MessageType]
        assert len(values) == len(set(values))

    def test_known_values(self) -> None:
        assert MessageType.AUTH == 0x01
        assert MessageType.EVENT_BATCH == 0x11
        assert MessageType.POLICY_PUSH == 0x30
        assert MessageType.ERROR == 0xFF

    def test_int_conversion(self) -> None:
        assert int(MessageType.HEARTBEAT) == 0x20
        assert MessageType(0x12) == MessageType.ACK


class TestEncodeFrame:
    def test_basic_roundtrip(self) -> None:
        msg = {"t": MessageType.AUTH, "id": 1, "ts": 1234567890.0, "p": {"api_key": "test"}}
        frame = encode_frame(msg)

        assert len(frame) > HEADER_SIZE
        payload_len = struct.unpack("!I", frame[:HEADER_SIZE])[0]
        assert payload_len == len(frame) - HEADER_SIZE

        decoded = decode_frame(frame[HEADER_SIZE:])
        assert decoded["t"] == MessageType.AUTH
        assert decoded["id"] == 1
        assert decoded["p"]["api_key"] == "test"

    def test_defaults_ts_and_id(self) -> None:
        before = time.time()
        frame = encode_frame({"t": MessageType.HEARTBEAT})
        after = time.time()

        decoded = decode_frame(frame[HEADER_SIZE:])
        assert decoded["id"] == 0
        assert before <= decoded["ts"] <= after
        assert decoded["p"] == {}

    def test_missing_type_raises(self) -> None:
        with pytest.raises(ValueError, match="must contain 't'"):
            encode_frame({"id": 1, "p": {}})

    def test_large_payload_raises(self) -> None:
        huge = {"t": MessageType.EVENT, "p": {"data": b"\x00" * (MAX_FRAME_SIZE + 1)}}
        with pytest.raises(ValueError, match="exceeds"):
            encode_frame(huge)


class TestDecodeFrame:
    def test_non_map_raises(self) -> None:
        data = msgpack.packb([1, 2, 3], use_bin_type=True)
        with pytest.raises(ValueError, match="Expected msgpack map"):
            decode_frame(data)

    def test_missing_type_raises(self) -> None:
        data = msgpack.packb({"id": 1, "p": {}}, use_bin_type=True)
        with pytest.raises(ValueError, match="missing 't'"):
            decode_frame(data)

    def test_preserves_nested_structures(self) -> None:
        payload = {
            "t": MessageType.EVENT,
            "id": 42,
            "ts": 1000.0,
            "p": {
                "event_id": "abc-123",
                "tools": [{"name": "cursor", "version": "0.48"}],
            },
        }
        raw = msgpack.packb(payload, use_bin_type=True)
        decoded = decode_frame(raw)
        assert decoded["p"]["tools"][0]["name"] == "cursor"


class TestFrameReader:
    def _make_frame(self, msg: dict) -> bytes:
        return encode_frame(msg)

    def test_single_message(self) -> None:
        reader = FrameReader()
        frame = self._make_frame({"t": MessageType.HEARTBEAT, "id": 1})
        reader.feed(frame)
        msgs = reader.messages()
        assert len(msgs) == 1
        assert msgs[0]["t"] == MessageType.HEARTBEAT

    def test_multiple_messages_in_one_feed(self) -> None:
        reader = FrameReader()
        frames = b""
        for i in range(5):
            frames += self._make_frame({"t": MessageType.EVENT, "id": i})
        reader.feed(frames)
        msgs = reader.messages()
        assert len(msgs) == 5
        assert [m["id"] for m in msgs] == list(range(5))

    def test_partial_feed(self) -> None:
        reader = FrameReader()
        frame = self._make_frame({"t": MessageType.ACK, "id": 10, "p": {"seq_ids": [1, 2]}})

        mid = len(frame) // 2
        reader.feed(frame[:mid])
        assert reader.messages() == []

        reader.feed(frame[mid:])
        msgs = reader.messages()
        assert len(msgs) == 1
        assert msgs[0]["id"] == 10

    def test_byte_by_byte_feed(self) -> None:
        reader = FrameReader()
        frame = self._make_frame({"t": MessageType.HEARTBEAT, "id": 99})
        for b in frame:
            reader.feed(bytes([b]))
        msgs = reader.messages()
        assert len(msgs) == 1
        assert msgs[0]["id"] == 99

    def test_oversized_frame_raises(self) -> None:
        reader = FrameReader()
        fake_header = struct.pack("!I", MAX_FRAME_SIZE + 1)
        reader.feed(fake_header)
        with pytest.raises(ValueError, match="exceeds limit"):
            reader.messages()

    def test_reset_clears_buffer(self) -> None:
        reader = FrameReader()
        frame = self._make_frame({"t": MessageType.HEARTBEAT})
        reader.feed(frame[:3])
        reader.reset()
        reader.feed(frame)
        msgs = reader.messages()
        assert len(msgs) == 1

    def test_interleaved_feed_and_consume(self) -> None:
        reader = FrameReader()

        reader.feed(self._make_frame({"t": MessageType.AUTH, "id": 1}))
        msgs = reader.messages()
        assert len(msgs) == 1

        reader.feed(self._make_frame({"t": MessageType.AUTH_OK, "id": 2}))
        reader.feed(self._make_frame({"t": MessageType.EVENT, "id": 3}))
        msgs = reader.messages()
        assert len(msgs) == 2
        assert msgs[0]["t"] == MessageType.AUTH_OK
        assert msgs[1]["t"] == MessageType.EVENT
