"""Detec Wire Protocol — shared binary protocol for agent-server communication.

This package is imported by both the collector (agent side) and the API
(server side) so the wire format stays in one place.
"""

__version__ = "0.1.0"

from protocol.wire import MessageType, encode_frame, decode_frame, FrameReader
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

__all__ = [
    "MessageType",
    "encode_frame",
    "decode_frame",
    "FrameReader",
    "auth_msg",
    "auth_ok_msg",
    "auth_fail_msg",
    "event_msg",
    "event_batch_msg",
    "ack_msg",
    "nack_msg",
    "heartbeat_msg",
    "heartbeat_ack_msg",
    "policy_push_msg",
    "command_msg",
    "command_ack_msg",
    "error_msg",
]
