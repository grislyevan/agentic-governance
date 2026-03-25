"""AgentBuild model — tracks uploaded agent MSI builds per tenant."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class AgentBuild(Base):
    __tablename__ = "agent_builds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
