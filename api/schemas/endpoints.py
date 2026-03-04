"""Endpoint Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EndpointCreate(BaseModel):
    hostname: str
    os_info: str | None = None
    posture: str = "unmanaged"


class EndpointResponse(BaseModel):
    id: str
    hostname: str
    os_info: str | None
    posture: str
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EndpointListResponse(BaseModel):
    total: int
    items: list[EndpointResponse]
