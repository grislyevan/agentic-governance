"""Endpoint profile Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EndpointProfileConfig(BaseModel):
    """Per-profile agent config (subset used in create/update)."""
    scan_interval_seconds: int = Field(default=300, ge=30, le=86400)
    enforcement_posture: str = Field(default="passive", max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)


class EndpointProfileCreate(BaseModel):
    name: str = Field(max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    scan_interval_seconds: int = Field(default=300, ge=30, le=86400)
    enforcement_posture: str = Field(default="passive", max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)


class EndpointProfileUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    slug: str | None = Field(default=None, max_length=64)
    scan_interval_seconds: int | None = Field(default=None, ge=30, le=86400)
    enforcement_posture: str | None = Field(default=None, max_length=16, pattern="^(passive|audit|active)$")
    auto_enforce_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    policy_set_id: str | None = Field(default=None, max_length=128)


class EndpointProfileResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    slug: str
    created_at: datetime
    scan_interval_seconds: int
    enforcement_posture: str
    auto_enforce_threshold: float
    policy_set_id: str | None

    model_config = {"from_attributes": True}


class EndpointProfileListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[EndpointProfileResponse]
