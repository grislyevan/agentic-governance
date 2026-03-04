"""Event Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventIngest(BaseModel):
    """Payload for POST /events — accepts the canonical event envelope."""
    event_id: str
    event_type: str
    event_version: str
    observed_at: datetime
    session_id: str | None = None
    trace_id: str | None = None
    parent_event_id: str | None = None
    tool: dict[str, Any] | None = None
    action: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    actor: dict[str, Any] | None = None
    endpoint: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    severity: dict[str, Any] | None = None


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
    payload: dict[str, Any]

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EventResponse]
