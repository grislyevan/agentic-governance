"""Tests for protocol.messages: typed message constructors."""

from __future__ import annotations

import time

import pytest

from protocol.wire import MessageType, encode_frame, decode_frame, HEADER_SIZE
from protocol.messages import (
    auth_msg,
    auth_ok_msg,
    auth_fail_msg,
    event_msg,
    event_batch_msg,
    ack_msg,
    nack_msg,
    heartbeat_msg,
    heartbeat_ack_msg,
    policy_push_msg,
    command_msg,
    command_ack_msg,
    error_msg,
)


def _roundtrip(msg: dict) -> dict:
    """Encode then decode a message through the wire format."""
    frame = encode_frame(msg)
    return decode_frame(frame[HEADER_SIZE:])


class TestAuth:
    def test_auth_msg(self) -> None:
        msg = auth_msg("key-123", "host1", "0.3.0", seq=1)
        assert msg["t"] == MessageType.AUTH
        assert msg["id"] == 1
        assert msg["p"]["api_key"] == "key-123"
        assert msg["p"]["hostname"] == "host1"
        assert msg["p"]["agent_version"] == "0.3.0"

    def test_auth_ok_msg(self) -> None:
        msg = auth_ok_msg("sess-1", "ep-1", "0.1.0", seq=2)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.AUTH_OK
        assert decoded["p"]["session_id"] == "sess-1"
        assert decoded["p"]["endpoint_id"] == "ep-1"

    def test_auth_fail_msg(self) -> None:
        msg = auth_fail_msg("invalid api key")
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.AUTH_FAIL
        assert decoded["p"]["reason"] == "invalid api key"


class TestEvents:
    def test_single_event(self) -> None:
        event = {"event_id": "ev-1", "event_type": "tool.detected", "tool_name": "cursor"}
        msg = event_msg(event, seq=10)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.EVENT
        assert decoded["id"] == 10
        assert decoded["p"]["event_id"] == "ev-1"

    def test_event_batch(self) -> None:
        events = [
            {"event_id": f"ev-{i}", "event_type": "tool.detected"}
            for i in range(5)
        ]
        msg = event_batch_msg(events, seq=20)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.EVENT_BATCH
        assert len(decoded["p"]) == 5
        assert decoded["p"][0]["event_id"] == "ev-0"
        assert decoded["p"][4]["event_id"] == "ev-4"

    def test_empty_batch(self) -> None:
        msg = event_batch_msg([], seq=1)
        decoded = _roundtrip(msg)
        assert decoded["p"] == []


class TestAcknowledgement:
    def test_ack_msg(self) -> None:
        msg = ack_msg([1, 2, 3], seq=5)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.ACK
        assert decoded["p"]["seq_ids"] == [1, 2, 3]

    def test_nack_msg(self) -> None:
        failures = [
            {"seq_id": 10, "reason": "schema validation failed"},
            {"seq_id": 11, "reason": "duplicate event_id"},
        ]
        msg = nack_msg(failures, seq=6)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.NACK
        assert len(decoded["p"]["failures"]) == 2
        assert decoded["p"]["failures"][0]["reason"] == "schema validation failed"


class TestHeartbeat:
    def test_heartbeat_empty(self) -> None:
        msg = heartbeat_msg(seq=1)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.HEARTBEAT
        assert decoded["p"] == {}

    def test_heartbeat_with_stats(self) -> None:
        stats = {"events_sent": 42, "uptime": 3600}
        msg = heartbeat_msg(stats, seq=2)
        decoded = _roundtrip(msg)
        assert decoded["p"]["events_sent"] == 42

    def test_heartbeat_ack(self) -> None:
        msg = heartbeat_ack_msg(next_expected_in=30, endpoint_status="active", seq=3)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.HEARTBEAT_ACK
        assert decoded["p"]["next_expected_in"] == 30
        assert decoded["p"]["endpoint_status"] == "active"


class TestServerPush:
    def test_policy_push(self) -> None:
        rules = [
            {"rule_id": "r1", "action": "alert", "tool_name": "ollama"},
            {"rule_id": "r2", "action": "block", "tool_class": "B"},
        ]
        msg = policy_push_msg(rules, seq=1)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.POLICY_PUSH
        assert len(decoded["p"]["rules"]) == 2

    def test_command_msg(self) -> None:
        msg = command_msg("scan_now", "cmd-abc", params={"force": True}, seq=5)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.COMMAND
        assert decoded["p"]["command"] == "scan_now"
        assert decoded["p"]["command_id"] == "cmd-abc"
        assert decoded["p"]["params"]["force"] is True

    def test_command_no_params(self) -> None:
        msg = command_msg("shutdown", "cmd-xyz", seq=6)
        decoded = _roundtrip(msg)
        assert decoded["p"]["params"] == {}

    def test_command_ack(self) -> None:
        msg = command_ack_msg("cmd-abc", "success", detail={"scanned": 12}, seq=7)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.COMMAND_ACK
        assert decoded["p"]["result"] == "success"
        assert decoded["p"]["detail"]["scanned"] == 12


class TestError:
    def test_error_msg(self) -> None:
        msg = error_msg(500, "internal error", seq=99)
        decoded = _roundtrip(msg)
        assert decoded["t"] == MessageType.ERROR
        assert decoded["p"]["code"] == 500
        assert decoded["p"]["message"] == "internal error"


class TestTimestamps:
    def test_timestamp_is_recent(self) -> None:
        before = time.time()
        msg = heartbeat_msg()
        after = time.time()
        assert before <= msg["ts"] <= after

    def test_explicit_timestamp_preserved(self) -> None:
        msg = {"t": MessageType.HEARTBEAT, "ts": 1000.5, "p": {}}
        decoded = _roundtrip(msg)
        assert decoded["ts"] == 1000.5


class TestSequenceNumbers:
    def test_default_seq_is_zero(self) -> None:
        msg = heartbeat_msg()
        assert msg["id"] == 0

    def test_explicit_seq(self) -> None:
        msg = event_msg({"event_id": "x"}, seq=999)
        assert msg["id"] == 999
