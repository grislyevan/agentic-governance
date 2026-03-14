"""Endpoint profile model: named groups with per-profile agent config."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from core.database import Base


class EndpointProfile(Base):
    """Named profile (e.g. Critical Server, Standard Workstation) with agent config.

    Endpoints can be assigned to a profile; heartbeat returns config from the
    profile when set, else tenant/endpoint defaults.
    """
    __tablename__ = "endpoint_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_endpoint_profiles_tenant_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Per-profile agent config (used when endpoint has this profile)
    scan_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=settings.default_heartbeat_interval
    )
    enforcement_posture: Mapped[str] = mapped_column(String(16), nullable=False, default="passive")
    auto_enforce_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.75)
    policy_set_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="endpoint_profiles")  # noqa: F821
    endpoints: Mapped[list["Endpoint"]] = relationship(  # noqa: F821
        "Endpoint", back_populates="endpoint_profile", lazy="select"
    )
