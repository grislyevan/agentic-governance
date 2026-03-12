"""Tenant model — top-level multi-tenancy boundary."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def generate_agent_key() -> str:
    """Generate a random tenant-level agent key (plaintext, 64 hex chars)."""
    return secrets.token_hex(32)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    agent_key: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True, default=90)

    # Billing (Stripe)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    subscription_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free", server_default="free")
    subscription_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", server_default="active")
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship("User", back_populates="tenant", lazy="select")  # noqa: F821
    endpoints: Mapped[list["Endpoint"]] = relationship("Endpoint", back_populates="tenant", lazy="select")  # noqa: F821
    events: Mapped[list["Event"]] = relationship("Event", back_populates="tenant", lazy="select")  # noqa: F821
    policies: Mapped[list["Policy"]] = relationship("Policy", back_populates="tenant", lazy="select")  # noqa: F821

    @property
    def is_trial(self) -> bool:
        if not self.trial_ends_at:
            return False
        return datetime.now(timezone.utc) < self.trial_ends_at

    @property
    def is_active_subscription(self) -> bool:
        return self.subscription_status in ("active", "trialing")
