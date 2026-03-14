"""Pydantic schemas for response playbooks."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_PAYLOAD_DEPTH = 4
MAX_PAYLOAD_SIZE = 65536  # 64KB for playbook test and trigger/actions


def _depth(obj: Any) -> int:
    """Return nesting depth: 0 for scalars, 1 + max child depth for dict/list."""
    if isinstance(obj, dict):
        return 1 + max((_depth(v) for v in obj.values()), default=0) if obj else 1
    if isinstance(obj, list):
        return 1 + max((_depth(v) for v in obj), default=0) if obj else 1
    return 0


class ResponsePlaybookCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=512)
    trigger: dict[str, Any] = Field(default_factory=dict)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    escalation: dict[str, Any] | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def check_trigger_actions_escalation_depth(self) -> "ResponsePlaybookCreate":
        for name, val in (("trigger", self.trigger), ("escalation", self.escalation)):
            if val is not None and _depth(val) > MAX_PAYLOAD_DEPTH:
                raise ValueError(f"{name} exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
        if self.actions is not None:
            for i, item in enumerate(self.actions):
                if _depth(item) > MAX_PAYLOAD_DEPTH:
                    raise ValueError(f"actions[{i}] exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
        return self


class ResponsePlaybookUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=512)
    trigger: dict[str, Any] | None = None
    actions: list[dict[str, Any]] | None = None
    escalation: dict[str, Any] | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def check_trigger_actions_escalation_depth(self) -> "ResponsePlaybookUpdate":
        for name, val in (("trigger", self.trigger), ("escalation", self.escalation)):
            if val is not None and _depth(val) > MAX_PAYLOAD_DEPTH:
                raise ValueError(f"{name} exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
        if self.actions is not None:
            for i, item in enumerate(self.actions):
                if _depth(item) > MAX_PAYLOAD_DEPTH:
                    raise ValueError(f"actions[{i}] exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
        return self


class ResponsePlaybookOut(BaseModel):
    id: str
    tenant_id: str
    name: str
    description: str | None
    trigger: dict[str, Any]
    actions: list[dict[str, Any]]
    escalation: dict[str, Any] | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResponsePlaybookListResponse(BaseModel):
    items: list[ResponsePlaybookOut]
    total: int


class PlaybookTestRequest(BaseModel):
    event_payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_payload")
    @classmethod
    def event_payload_limits(cls, v: dict[str, Any]) -> dict[str, Any]:
        if _depth(v) > MAX_PAYLOAD_DEPTH:
            raise ValueError(f"event_payload exceeds max nesting depth {MAX_PAYLOAD_DEPTH}")
        if len(json.dumps(v)) > MAX_PAYLOAD_SIZE:
            raise ValueError("event_payload exceeds max size 64KB")
        return v


class PlaybookTestResponse(BaseModel):
    playbook_id: str
    matched: bool
    actions_run: list[dict[str, Any]]
