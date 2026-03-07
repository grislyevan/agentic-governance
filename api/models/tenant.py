"""Tenant model — top-level multi-tenancy boundary."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
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
