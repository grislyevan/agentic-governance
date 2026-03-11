"""Policy model — tenant-level enforcement rules.

Baseline rules are seeded on tenant creation and carry ``is_baseline=True``.
They can be toggled (is_active) but not deleted or have their rule_id changed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(16), nullable=False, default="0.4.0")
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_baseline: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="policies")  # noqa: F821
