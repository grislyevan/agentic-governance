"""Endpoint Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EndpointCreate(BaseModel):
    hostname: str = Field(max_length=255)
    os_info: str | None = Field(default=None, max_length=512)
    management_state: str = Field(default="unmanaged", max_length=32)


class EndpointUpdate(BaseModel):
    endpoint_profile_id: str | None = Field(default=None, max_length=36)
    management_state: str | None = Field(default=None, max_length=32)


class EndpointResponse(BaseModel):
    id: str
    hostname: str
    os_info: str | None
    management_state: str
    endpoint_profile_id: str | None = None
    enforcement_posture: str = "passive"
    auto_enforce_threshold: float = 0.75
    telemetry_provider: str | None = None
    status: str
    heartbeat_interval: int
    last_seen_at: datetime | None
    created_at: datetime
    is_stale: bool = False

    model_config = {"from_attributes": True}


class EndpointListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EndpointResponse]


class EndpointStatusResponse(BaseModel):
    id: str
    hostname: str
    status: str
    last_seen_at: datetime | None
    heartbeat_interval: int
    seconds_since_heartbeat: float | None
    is_stale: bool = False

    model_config = {"from_attributes": True}
