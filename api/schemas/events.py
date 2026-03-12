"""Event Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EventIngest(BaseModel):
    """Payload for POST /events: accepts the canonical event envelope."""
    event_id: str = Field(max_length=36)
    event_type: str = Field(max_length=64)
    event_version: str = Field(max_length=16)
    observed_at: datetime
    session_id: str | None = Field(default=None, max_length=36)
    trace_id: str | None = Field(default=None, max_length=64)
    parent_event_id: str | None = Field(default=None, max_length=36)
    tool: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    actor: dict[str, Any] | None = None
    endpoint: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    severity: dict[str, Any] | None = None
    enforcement: dict[str, Any] | None = None
    outcome: dict[str, Any] | None = None
    posture: dict[str, Any] | None = None
    mitre_attack: dict[str, Any] | None = None

    # Payload signing (Feature 4)
    signature: str | None = Field(default=None, alias="_signature")
    key_fingerprint: str | None = Field(default=None, alias="_key_fingerprint")

    model_config = {"populate_by_name": True}


class EventResponse(BaseModel):
    id: str
    event_id: str
    event_type: str
    event_version: str
    observed_at: datetime
    tool_name: str | None
    tool_class: str | None
    tool_version: str | None
    attribution_confidence: float | None
    decision_state: str | None
    rule_id: str | None
    severity_level: str | None
    signature_verified: bool | None = None
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EventResponse]
