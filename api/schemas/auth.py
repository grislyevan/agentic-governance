"""Auth Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None
    tenant_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def full_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError("Full name must be at most 255 characters")
        return v

    @field_validator("tenant_name")
    @classmethod
    def tenant_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 255:
            raise ValueError("Tenant name must be at most 255 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v: str) -> str:
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(TokenResponse):
    """Returned only on registration; includes the raw API key (shown once)."""
    api_key: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str | None
    role: str
    tenant_id: str

    model_config = {"from_attributes": True}
