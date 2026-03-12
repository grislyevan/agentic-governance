"""Typed message constructors for the Detec Wire Protocol.

Each function returns a dict ready to pass to ``encode_frame()``.
Sequence IDs (``seq``) are caller-assigned for ack correlation.
"""

from __future__ import annotations

import time
from typing import Any

from protocol.wire import MessageType


def _envelope(msg_type: MessageType, seq: int, payload: Any) -> dict[str, Any]:
    return {"t": msg_type, "id": seq, "ts": time.time(), "p": payload}


# -- Authentication ----------------------------------------------------------

def auth_msg(
    api_key: str,
    hostname: str,
    agent_version: str,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Agent -> Server: authenticate this connection."""
    return _envelope(MessageType.AUTH, seq, {
        "api_key": api_key,
        "hostname": hostname,
        "agent_version": agent_version,
    })


def auth_ok_msg(
    session_id: str,
    endpoint_id: str,
    server_version: str,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: authentication succeeded."""
    return _envelope(MessageType.AUTH_OK, seq, {
        "session_id": session_id,
        "endpoint_id": endpoint_id,
        "server_version": server_version,
    })


def auth_fail_msg(reason: str, *, seq: int = 0) -> dict[str, Any]:
    """Server -> Agent: authentication failed."""
    return _envelope(MessageType.AUTH_FAIL, seq, {"reason": reason})


# -- Events ------------------------------------------------------------------

def event_msg(event: dict[str, Any], *, seq: int = 0) -> dict[str, Any]:
    """Agent -> Server: a single canonical event."""
    return _envelope(MessageType.EVENT, seq, event)


def event_batch_msg(events: list[dict[str, Any]], *, seq: int = 0) -> dict[str, Any]:
    """Agent -> Server: a batch of canonical events."""
    return _envelope(MessageType.EVENT_BATCH, seq, events)


# -- Acknowledgement ---------------------------------------------------------

def ack_msg(seq_ids: list[int], *, seq: int = 0) -> dict[str, Any]:
    """Server -> Agent: these sequence IDs were persisted."""
    return _envelope(MessageType.ACK, seq, {"seq_ids": seq_ids})


def nack_msg(
    failures: list[dict[str, Any]],
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: these sequence IDs failed.

    ``failures`` is a list of ``{"seq_id": int, "reason": str}`` dicts.
    """
    return _envelope(MessageType.NACK, seq, {"failures": failures})


# -- Heartbeat ---------------------------------------------------------------

def heartbeat_msg(stats: dict[str, Any] | None = None, *, seq: int = 0) -> dict[str, Any]:
    """Agent -> Server: keepalive with optional agent stats."""
    return _envelope(MessageType.HEARTBEAT, seq, stats or {})


def heartbeat_ack_msg(
    next_expected_in: int,
    endpoint_status: str,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: heartbeat acknowledged."""
    return _envelope(MessageType.HEARTBEAT_ACK, seq, {
        "next_expected_in": next_expected_in,
        "endpoint_status": endpoint_status,
    })


# -- Server push -------------------------------------------------------------

def policy_push_msg(rules: list[dict[str, Any]], *, seq: int = 0) -> dict[str, Any]:
    """Server -> Agent: updated policy rules."""
    return _envelope(MessageType.POLICY_PUSH, seq, {"rules": rules})


def posture_push_msg(
    posture: str,
    auto_enforce_threshold: float = 0.75,
    allow_list: list[str] | None = None,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: set enforcement posture and allow-list."""
    return _envelope(MessageType.POSTURE_PUSH, seq, {
        "posture": posture,
        "auto_enforce_threshold": auto_enforce_threshold,
        "allow_list": allow_list or [],
    })


def command_msg(
    command: str,
    command_id: str,
    params: dict[str, Any] | None = None,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Server -> Agent: execute a command (scan_now, update_config, shutdown)."""
    return _envelope(MessageType.COMMAND, seq, {
        "command": command,
        "command_id": command_id,
        "params": params or {},
    })


def command_ack_msg(
    command_id: str,
    result: str,
    detail: dict[str, Any] | None = None,
    *,
    seq: int = 0,
) -> dict[str, Any]:
    """Agent -> Server: command execution result."""
    return _envelope(MessageType.COMMAND_ACK, seq, {
        "command_id": command_id,
        "result": result,
        "detail": detail or {},
    })


# -- Error -------------------------------------------------------------------

def error_msg(code: int, message: str, *, seq: int = 0) -> dict[str, Any]:
    """Either direction: protocol-level error."""
    return _envelope(MessageType.ERROR, seq, {"code": code, "message": message})
