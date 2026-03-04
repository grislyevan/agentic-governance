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
    status: str
    heartbeat_interval: int
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EndpointListResponse(BaseModel):
    total: int
    items: list[EndpointResponse]


class EndpointStatusResponse(BaseModel):
    id: str
    hostname: str
    status: str
    last_seen_at: datetime | None
    heartbeat_interval: int
    seconds_since_heartbeat: float | None

    model_config = {"from_attributes": True}
