"""Event model — stores canonical detection/policy/enforcement events."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_tenant_observed", "tenant_id", "observed_at"),
        Index("ix_events_endpoint_type", "endpoint_id", "event_type"),
        Index("ix_events_tool_name", "tool_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    endpoint_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("endpoints.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_version: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(36))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    parent_event_id: Mapped[str | None] = mapped_column(String(36))

    # Tool attribution
    tool_name: Mapped[str | None] = mapped_column(String(128))
    tool_class: Mapped[str | None] = mapped_column(String(4))
    tool_version: Mapped[str | None] = mapped_column(String(64))
    attribution_confidence: Mapped[float | None]
    attribution_sources: Mapped[str | None] = mapped_column(Text)

    # Policy decision
    decision_state: Mapped[str | None] = mapped_column(String(32))
    rule_id: Mapped[str | None] = mapped_column(String(32))
    severity_level: Mapped[str | None] = mapped_column(String(4))

    # Signature verification
    signature_verified: Mapped[bool | None] = mapped_column(Boolean)

    # Full canonical event payload
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="events")  # noqa: F821
    endpoint: Mapped["Endpoint | None"] = relationship("Endpoint", back_populates="events")  # noqa: F821
