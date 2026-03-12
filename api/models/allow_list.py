"""Allow-list model for enforcement exemptions.

Entries in this table are never enforced against, even in active posture.
Pattern types: 'name' (process name substring), 'path' (binary path prefix),
'hash' (SHA-256 of binary).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class AllowListEntry(Base):
    __tablename__ = "allow_list_entries"
    __table_args__ = (UniqueConstraint("tenant_id", "pattern", "pattern_type", name="uq_allow_list_tenant_pattern_type"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False, index=True)
    pattern: Mapped[str] = mapped_column(String(512), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(16), nullable=False, default="name")
    description: Mapped[str | None] = mapped_column(String(512))
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
