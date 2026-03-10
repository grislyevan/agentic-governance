"""User management Pydantic schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, field_validator

from models.user import VALID_ROLES

_ASSIGNABLE_ROLES = ("admin", "analyst", "viewer")


class UserCreate(BaseModel):
    first_name: str
    last_name: str | None = None
    email: EmailStr
    role: str = "analyst"
    password: str | None = None

    @field_validator("first_name")
    @classmethod
    def first_name_length(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 128:
            raise ValueError("First name is required and must be at most 128 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_length(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) > 128:
                raise ValueError("Last name must be at most 128 characters")
            return v or None
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in _ASSIGNABLE_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(_ASSIGNABLE_ROLES)}")
        return v

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str | None) -> str | None:
        if v is not None:
            if len(v) < 8:
                raise ValueError("Password must be at least 8 characters")
            if len(v) > 128:
                raise ValueError("Password must be at most 128 characters")
        return v


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    role: str | None = None
    is_active: bool | None = None

    @field_validator("first_name")
    @classmethod
    def first_name_length(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v or len(v) > 128:
                raise ValueError("First name must be non-empty and at most 128 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_length(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if len(v) > 128:
                raise ValueError("Last name must be at most 128 characters")
            return v or None
        return v

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in _ASSIGNABLE_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(_ASSIGNABLE_ROLES)}")
        return v


class UserOut(BaseModel):
    id: str
    first_name: str | None
    last_name: str | None
    email: str
    role: str
    is_active: bool
    auth_provider: str
    password_reset_required: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class UserCreateResponse(UserOut):
    """Returned when creating a user via invite. Includes the one-time invite token."""
    invite_token: str | None = None


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    per_page: int
