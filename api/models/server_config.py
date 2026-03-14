"""Server-wide configuration (e.g. TCP gateway). Single row, keyed by id=1."""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class ServerConfig(Base):
    """Singleton row: gateway port, host, and enabled flag. Null means use env default."""

    __tablename__ = "server_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    gateway_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gateway_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gateway_enabled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
