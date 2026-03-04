"""Endpoint model — represents a monitored workstation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as tz

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base

ENDPOINT_STATUS_ACTIVE = "active"
ENDPOINT_STATUS_STALE = "stale"
ENDPOINT_STATUS_UNGOVERNED = "ungoverned"
ENDPOINT_STATUS_DECOMMISSIONED = "decommissioned"


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os_info: Mapped[str | None] = mapped_column(String(512))
    posture: Mapped[str] = mapped_column(String(32), nullable=False, default="unmanaged")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ENDPOINT_STATUS_ACTIVE)
    heartbeat_interval: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Cryptographic enrollment (Feature 4)
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    key_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="endpoints")  # noqa: F821
    events: Mapped[list["Event"]] = relationship("Event", back_populates="endpoint", lazy="select")  # noqa: F821

    def compute_status(self) -> str:
        """Derive endpoint status from heartbeat timing."""
        if self.status == ENDPOINT_STATUS_DECOMMISSIONED:
            return ENDPOINT_STATUS_DECOMMISSIONED
        if self.last_seen_at is None:
            return ENDPOINT_STATUS_UNGOVERNED

        now = datetime.now(tz.utc)
        elapsed = (now - self.last_seen_at).total_seconds()
        threshold = self.heartbeat_interval * 1.5

        if elapsed <= threshold:
            return ENDPOINT_STATUS_ACTIVE
        if elapsed <= threshold * 3:
            return ENDPOINT_STATUS_STALE
        return ENDPOINT_STATUS_UNGOVERNED
