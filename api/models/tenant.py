"""Tenant model — top-level multi-tenancy boundary."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base

AGENT_KEY_PREFIX_LEN = 8


def _hash_agent_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_agent_key() -> tuple[str, str, str]:
    """Generate a random tenant-level agent key.

    Returns (raw_key, prefix, hash) so the raw key can be displayed once
    and only the prefix + hash are persisted.
    """
    raw = secrets.token_hex(32)
    return raw, raw[:AGENT_KEY_PREFIX_LEN], _hash_agent_key(raw)


def verify_agent_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw agent key against the stored hash."""
    return hmac.compare_digest(_hash_agent_key(raw_key), stored_hash)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_key: Mapped[str | None] = mapped_column(String(128))
    agent_key_prefix: Mapped[str | None] = mapped_column(String(16))
    agent_key_hash: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="select")  # noqa: F821
    endpoints: Mapped[list["Endpoint"]] = relationship("Endpoint", back_populates="tenant", lazy="select")  # noqa: F821
    events: Mapped[list["Event"]] = relationship("Event", back_populates="tenant", lazy="select")  # noqa: F821
    policies: Mapped[list["Policy"]] = relationship("Policy", back_populates="tenant", lazy="select")  # noqa: F821
