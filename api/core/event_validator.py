"""Server-side event payload validation.

Validates incoming event payloads before persistence. Applies structural
checks to prevent arbitrarily deep, oversized, or malicious data from
being stored.

Enum values (event_type, tool.class, severity.level) are logged as
warnings but not rejected, since older collectors may emit non-canonical
values. Only structural issues (depth, size, type mismatches) cause
hard rejections.

Used by both the HTTP ingest route and the TCP gateway.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_NESTED_DEPTH = 4
_MAX_PAYLOAD_KEYS = 50
_MAX_STRING_VALUE_LEN = 2048
_MAX_PAYLOAD_SIZE_ESTIMATE = 65536

_ALLOWED_TOP_LEVEL_KEYS = frozenset({
    "event_id", "event_type", "event_version", "observed_at", "ingested_at",
    "session_id", "trace_id", "parent_event_id",
    "actor", "endpoint", "tool", "action", "target",
    "policy", "approval", "exception", "evidence",
    "enforcement", "outcome", "severity", "posture",
    "mitre_attack", "correlation_context", "telemetry_providers",
    "session_timeline",
    "_signature", "_key_fingerprint",
    "signature", "key_fingerprint",
})


def _check_depth(obj: Any, max_depth: int, current: int = 0) -> bool:
    """Return True if obj nesting is within max_depth."""
    if current > max_depth:
        return False
    if isinstance(obj, dict):
        return all(_check_depth(v, max_depth, current + 1) for v in obj.values())
    if isinstance(obj, list):
        return all(_check_depth(v, max_depth, current + 1) for v in obj)
    return True


def validate_event_payload(data: dict[str, Any]) -> list[str]:
    """Validate an event payload dict. Returns a list of error strings (empty = valid).

    Hard rejects: non-dict payload, excessive keys, excessive nesting depth,
    unknown top-level keys, wrong types for nested blocks.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Payload must be a JSON object"]

    unknown_keys = set(data.keys()) - _ALLOWED_TOP_LEVEL_KEYS
    if unknown_keys:
        errors.append(f"Unknown top-level keys: {', '.join(sorted(unknown_keys))}")

    if len(data) > _MAX_PAYLOAD_KEYS:
        errors.append(f"Payload has {len(data)} keys, max {_MAX_PAYLOAD_KEYS}")

    if not _check_depth(data, _MAX_NESTED_DEPTH):
        errors.append(f"Payload exceeds max nesting depth of {_MAX_NESTED_DEPTH}")

    for field in ("tool", "actor", "endpoint", "policy", "severity",
                   "action", "target", "enforcement", "outcome",
                   "approval", "exception", "evidence", "posture", "mitre_attack"):
        val = data.get(field)
        if val is not None and not isinstance(val, dict):
            errors.append(f"'{field}' must be an object, got {type(val).__name__}")

    tool = data.get("tool")
    if isinstance(tool, dict):
        conf = tool.get("attribution_confidence")
        if conf is not None:
            try:
                conf_f = float(conf)
                if not (0 <= conf_f <= 1):
                    errors.append("tool.attribution_confidence must be between 0 and 1")
            except (TypeError, ValueError):
                errors.append("tool.attribution_confidence must be a number")

    session_timeline = data.get("session_timeline")
    if session_timeline is not None:
        if not isinstance(session_timeline, list):
            errors.append("session_timeline must be an array")
        elif len(session_timeline) > 200:
            errors.append("session_timeline exceeds max length of 200")

    enforcement = data.get("enforcement")
    if isinstance(enforcement, dict):
        for str_field in ("detail", "cmdline_snippet", "process_name", "tactic"):
            val = enforcement.get(str_field)
            if isinstance(val, str) and len(val) > _MAX_STRING_VALUE_LEN:
                errors.append(
                    f"enforcement.{str_field} exceeds max length of {_MAX_STRING_VALUE_LEN}"
                )
        pids = enforcement.get("pids_killed")
        if pids is not None:
            if not isinstance(pids, list):
                errors.append("enforcement.pids_killed must be an array")
            elif len(pids) > 1000:
                errors.append("enforcement.pids_killed exceeds max length of 1000")

    try:
        size = len(json.dumps(data, default=str))
    except (TypeError, ValueError):
        size = 0
    if size > _MAX_PAYLOAD_SIZE_ESTIMATE:
        errors.append(f"Payload exceeds max size of {_MAX_PAYLOAD_SIZE_ESTIMATE} bytes")

    return errors
