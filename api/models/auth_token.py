"""Auth tokens for invite and password-reset flows."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

VALID_PURPOSES = ("invite", "reset")
DEFAULT_TOKEN_EXPIRY_HOURS = 24
RESET_TOKEN_EXPIRY_HOURS = 1


def generate_token() -> tuple[str, str]:
    """Generate a random token. Returns (raw_token, sha256_hash)."""
    raw = secrets.token_urlsafe(48)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def hash_token(raw: str) -> str:
    """SHA-256 hash of a raw token for lookup."""
    return hashlib.sha256(raw.encode()).hexdigest()


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(16), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        exp = self.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return now > exp

    @property
    def is_used(self) -> bool:
        return self.used_at is not None

    @property
    def is_valid(self) -> bool:
        return not self.is_expired and not self.is_used

    @classmethod
    def create_invite_token(cls, user_id: str) -> tuple["AuthToken", str]:
        """Create an invite token. Returns (model_instance, raw_token)."""
        raw, hashed = generate_token()
        token = cls(
            user_id=user_id,
            token_hash=hashed,
            purpose="invite",
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=DEFAULT_TOKEN_EXPIRY_HOURS),
        )
        return token, raw

    @classmethod
    def create_reset_token(cls, user_id: str) -> tuple["AuthToken", str]:
        """Create a password-reset token. Returns (model_instance, raw_token)."""
        raw, hashed = generate_token()
        token = cls(
            user_id=user_id,
            token_hash=hashed,
            purpose="reset",
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS),
        )
        return token, raw
