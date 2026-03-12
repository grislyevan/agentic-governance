"""Tenant management Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


class TenantCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 255:
            raise ValueError("Name is required and must be at most 255 characters")
        return v


class TenantUpdate(BaseModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 255:
                raise ValueError("Name must be non-empty and at most 255 characters")
        return v


class TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    subscription_tier: str
    member_count: int = 0
    endpoint_count: int = 0
    created_at: datetime
    role: str | None = None

    model_config = {"from_attributes": True}


class TenantSwitchRequest(BaseModel):
    tenant_id: str


class TenantSwitchResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant: TenantOut
