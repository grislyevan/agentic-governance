"""Effective server config: DB overrides with env fallback."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from core.config import settings
from models.server_config import ServerConfig


@dataclass
class GatewayConfig:
    enabled: bool
    host: str
    port: int


def get_effective_gateway_config(db: Session) -> GatewayConfig:
    """Return gateway settings: DB row overrides env, null means use env."""
    try:
        row = db.query(ServerConfig).filter(ServerConfig.id == 1).first()
    except Exception:
        row = None
    if row is None:
        return GatewayConfig(
            enabled=settings.gateway_enabled,
            host=settings.gateway_host,
            port=settings.gateway_port,
        )
    return GatewayConfig(
        enabled=row.gateway_enabled if row.gateway_enabled is not None else settings.gateway_enabled,
        host=row.gateway_host if row.gateway_host is not None else settings.gateway_host,
        port=row.gateway_port if row.gateway_port is not None else settings.gateway_port,
    )
