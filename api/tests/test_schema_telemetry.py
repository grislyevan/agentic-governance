"""Tests for telemetry_providers schema validation."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "canonical-event-schema.json"


def _load_schema() -> dict:
    with open(_SCHEMA_PATH) as f:
        return json.load(f)


def _minimal_valid_event(**overrides) -> dict:
    base = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "event_type": "detection.observed",
        "event_version": "1.0.0",
        "observed_at": "2026-03-10T12:00:00Z",
        "ingested_at": "2026-03-10T12:00:01Z",
        "session_id": "sess-001",
        "trace_id": "trace-001",
        "actor": {
            "id": "user@test.com",
            "type": "human",
            "trust_tier": "T1",
            "identity_confidence": 0.8,
            "org_context": "org",
        },
        "endpoint": {
            "id": "host-001",
            "os": "macOS 14",
            "posture": "managed",
        },
        "tool": {
            "name": "Cursor",
            "class": "C",
            "version": "0.1.0",
            "attribution_confidence": 0.75,
            "attribution_sources": ["process", "file"],
        },
        "action": {
            "type": "exec",
            "risk_class": "R2",
            "summary": "Tool execution detected",
            "raw_ref": "evidence://test",
        },
        "target": {
            "type": "host",
            "id": "host-001",
            "scope": "local",
            "sensitivity_tier": "Tier1",
        },
    }
    base.update(overrides)
    return base


class TestTelemetryProvidersSchema:
    def test_event_without_telemetry_providers_passes(self):
        """Events without telemetry_providers field are valid (optional)."""
        schema = _load_schema()
        event = _minimal_valid_event()
        jsonschema.validate(event, schema)

    def test_event_with_valid_telemetry_providers_passes(self):
        """Events with valid telemetry_providers pass validation."""
        schema = _load_schema()
        event = _minimal_valid_event(
            telemetry_providers=[
                {
                    "name": "detec-agent",
                    "type": "polling",
                    "layers": ["process", "file", "network"],
                },
                {
                    "name": "crowdstrike",
                    "type": "edr",
                    "layers": ["process", "network"],
                    "query_window": "2026-03-10T11:55:00Z/2026-03-10T12:01:00Z",
                },
            ]
        )
        jsonschema.validate(event, schema)

    def test_telemetry_providers_invalid_type_rejected(self):
        """Invalid type enum in telemetry_providers is rejected."""
        schema = _load_schema()
        event = _minimal_valid_event(
            telemetry_providers=[
                {
                    "name": "bad-provider",
                    "type": "invalid",
                    "layers": ["process"],
                },
            ]
        )
        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(event, schema)
        assert "invalid" in str(exc_info.value).lower() or "type" in str(exc_info.value).lower()

    def test_telemetry_providers_invalid_layer_rejected(self):
        """Invalid layer enum in telemetry_providers is rejected."""
        schema = _load_schema()
        event = _minimal_valid_event(
            telemetry_providers=[
                {
                    "name": "bad-provider",
                    "type": "edr",
                    "layers": ["invalid_layer"],
                },
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)

    def test_telemetry_providers_missing_required_rejected(self):
        """telemetry_providers entry missing required fields is rejected."""
        schema = _load_schema()
        event = _minimal_valid_event(
            telemetry_providers=[
                {
                    "name": "incomplete",
                    "type": "edr",
                    # missing "layers" which is required
                },
            ]
        )
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(event, schema)
