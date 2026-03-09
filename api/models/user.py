"""User model with role-based access within a tenant."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

API_KEY_PREFIX_LEN = 8

VALID_ROLES = ("owner", "admin", "analyst", "viewer")


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of the raw API key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate a new API key.  Returns (raw_key, prefix, hash)."""
    raw = secrets.token_hex(32)
    return raw, raw[:API_KEY_PREFIX_LEN], hash_api_key(raw)


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw key against the stored hash."""
    return hmac.compare_digest(hash_api_key(raw_key), stored_hash)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="analyst")
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    password_reset_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    api_key_prefix: Mapped[str | None] = mapped_column(String(8), index=True)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    refresh_jti: Mapped[str | None] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")  # noqa: F821

    @property
    def display_name(self) -> str:
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) or self.email
