"""Endpoint model — represents a monitored workstation."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone as tz

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from core.database import Base

ENDPOINT_STATUS_ACTIVE = "active"
ENDPOINT_STATUS_STALE = "stale"
ENDPOINT_STATUS_UNGOVERNED = "ungoverned"
ENDPOINT_STATUS_DECOMMISSIONED = "decommissioned"


class Endpoint(Base):
    """Monitored workstation.

    management_state: Whether this endpoint is under Detec governance (managed/unmanaged).
    enforcement_posture: How the agent acts on block decisions (passive/audit/active).
    Controlled centrally by admin.
    """
    __tablename__ = "endpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "hostname", name="uq_endpoints_tenant_hostname"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    endpoint_profile_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("endpoint_profiles.id"), nullable=True, index=True
    )
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    os_info: Mapped[str | None] = mapped_column(String(512))
    management_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unmanaged")
    enforcement_posture: Mapped[str] = mapped_column(String(16), nullable=False, default="passive")
    auto_enforce_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ENDPOINT_STATUS_ACTIVE)
    heartbeat_interval: Mapped[int] = mapped_column(
        Integer, nullable=False, default=settings.default_heartbeat_interval
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Telemetry provider reported by the agent (esf, etw, ebpf, polling)
    telemetry_provider: Mapped[str | None] = mapped_column(String(32))

    # EDR/MDM enforcement delegation (Phase 6)
    edr_host_id: Mapped[str | None] = mapped_column(String(255))
    enforcement_provider: Mapped[str | None] = mapped_column(String(64))

    # Services disabled by anti-resurrection escalation, reported by agent
    disabled_services: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)
    # Pending restore commands queued by admin, delivered to agent on next heartbeat
    pending_restore_services: Mapped[list | None] = mapped_column(JSON, nullable=True, default=None)

    # Cryptographic enrollment (Feature 4)
    signing_public_key: Mapped[str | None] = mapped_column(Text)
    key_fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)
    enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="endpoints")  # noqa: F821
    endpoint_profile: Mapped["EndpointProfile | None"] = relationship(  # noqa: F821
        "EndpointProfile", back_populates="endpoints", lazy="select"
    )
    events: Mapped[list["Event"]] = relationship("Event", back_populates="endpoint", lazy="select")  # noqa: F821

    def compute_status(self) -> str:
        """Derive endpoint status from heartbeat timing."""
        if self.status == ENDPOINT_STATUS_DECOMMISSIONED:
            return ENDPOINT_STATUS_DECOMMISSIONED
        if self.last_seen_at is None:
            return ENDPOINT_STATUS_UNGOVERNED

        now = datetime.now(tz.utc)
        last = self.last_seen_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=tz.utc)
        elapsed = (now - last).total_seconds()
        threshold = self.heartbeat_interval * 1.5

        if elapsed <= threshold:
            return ENDPOINT_STATUS_ACTIVE
        if elapsed <= threshold * 3:
            return ENDPOINT_STATUS_STALE
        return ENDPOINT_STATUS_UNGOVERNED

    @property
    def is_stale(self) -> bool:
        """True if last_seen_at is older than configured stale_threshold_days."""
        if self.last_seen_at is None:
            return True
        now = datetime.now(tz.utc)
        last = self.last_seen_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=tz.utc)
        return (now - last).days >= settings.stale_threshold_days
