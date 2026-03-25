"""ApprovalRequest model — tracks approval_required policy decisions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("endpoints.id", ondelete="SET NULL"), nullable=True
    )
    event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    policy_rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    requester_type: Mapped[str] = mapped_column(String(16), nullable=False, default="agent")
    decided_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
    endpoint: Mapped["Endpoint | None"] = relationship("Endpoint")  # noqa: F821
    decided_by_user: Mapped["User | None"] = relationship("User", foreign_keys=[decided_by])  # noqa: F821
