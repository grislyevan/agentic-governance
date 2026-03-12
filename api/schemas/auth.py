"""Auth Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None
    tenant_name: str | None = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v

    @field_validator("first_name")
    @classmethod
    def first_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 128:
            raise ValueError("First name must be at most 128 characters")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 128:
            raise ValueError("Last name must be at most 128 characters")
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
    refresh_token: str = Field(max_length=2048)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(max_length=512)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v


class AcceptInviteRequest(BaseModel):
    token: str = Field(max_length=512)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("Password must be at most 128 characters")
        return v


class PasswordResetResponse(BaseModel):
    message: str


class LoginResponse(TokenResponse):
    password_reset_required: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    tenant_id: str
    auth_provider: str
    password_reset_required: bool = False

    model_config = {"from_attributes": True}
