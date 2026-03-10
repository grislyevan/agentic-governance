"""Webhook Pydantic schemas."""

from __future__ import annotations

import ipaddress
import os
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, HttpUrl

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _validate_webhook_url(v: str) -> str:
    v = v.strip()
    env = os.getenv("ENV", "development").lower()
    is_prod = env in ("production", "staging")

    if is_prod:
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use https:// in production")
    else:
        if not v.startswith(("https://", "http://")):
            raise ValueError("Webhook URL must start with https:// or http://")

    if len(v) > 2048:
        raise ValueError("URL must be at most 2048 characters")

    parsed = urlparse(v)
    hostname = parsed.hostname or ""
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError("Webhook URL must not target private or link-local addresses")
    except ValueError as e:
        if "must not target" in str(e):
            raise
    return v


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = []
    is_active: bool = True

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        return _validate_webhook_url(v)


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    is_active: bool | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_webhook_url(v)
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
