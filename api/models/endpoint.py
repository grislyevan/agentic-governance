"""Endpoint model — represents a monitored workstation."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os_info: Mapped[str | None] = mapped_column(String(512))
    posture: Mapped[str] = mapped_column(String(32), nullable=False, default="unmanaged")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="endpoints")  # noqa: F821
    events: Mapped[list["Event"]] = relationship("Event", back_populates="endpoint", lazy="select")  # noqa: F821
