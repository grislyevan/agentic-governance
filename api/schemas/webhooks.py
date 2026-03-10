"""Webhook Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator, HttpUrl


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = []
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith(("https://", "http://")):
            raise ValueError("Webhook URL must start with https:// or http://")
        if len(v) > 2048:
            raise ValueError("URL must be at most 2048 characters")
        return v


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v.startswith(("https://", "http://")):
                raise ValueError("Webhook URL must start with https:// or http://")
            if len(v) > 2048:
                raise ValueError("URL must be at most 2048 characters")
        return v


class WebhookOut(BaseModel):
    id: str
    url: str
    events: list[str]
    secret: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("events", mode="before")
    @classmethod
    def parse_events(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []


class WebhookListResponse(BaseModel):
    items: list[WebhookOut]
    total: int
