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

import logging
from typing import Any

logger = logging.getLogger(__name__)

_MAX_NESTED_DEPTH = 4
_MAX_PAYLOAD_KEYS = 50

_ALLOWED_TOP_LEVEL_KEYS = frozenset({
    "event_id", "event_type", "event_version", "observed_at", "ingested_at",
    "session_id", "trace_id", "parent_event_id",
    "actor", "endpoint", "tool", "action", "target",
    "policy", "approval", "exception", "evidence",
    "enforcement", "outcome", "severity",
    "telemetry_providers",
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
                   "approval", "exception", "evidence"):
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

    return errors
