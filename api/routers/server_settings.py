"""Server-wide settings (TCP gateway port, host, enabled). Owner/admin can view; owner can update."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.server_config import GatewayConfig, get_effective_gateway_config
from core.tenant import resolve_auth, require_role
from models.server_config import ServerConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/server", tags=["server"])


class ServerGatewaySettingsResponse(BaseModel):
    gateway_enabled: bool
    gateway_host: str
    gateway_port: int


class ServerGatewaySettingsUpdate(BaseModel):
    gateway_enabled: bool | None = None
    gateway_host: str | None = None
    gateway_port: int | None = Field(default=None, ge=1, le=65535)


@router.get("/settings", response_model=ServerGatewaySettingsResponse)
def get_server_settings(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ServerGatewaySettingsResponse:
    """Return effective TCP gateway settings (DB overrides env). Admin or owner."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    cfg = get_effective_gateway_config(db)
    return ServerGatewaySettingsResponse(
        gateway_enabled=cfg.enabled,
        gateway_host=cfg.host,
        gateway_port=cfg.port,
    )


@router.put("/settings", response_model=ServerGatewaySettingsResponse)
async def update_server_settings(
    body: ServerGatewaySettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ServerGatewaySettingsResponse:
    """Update TCP gateway settings and restart the gateway. Owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")

    row = db.query(ServerConfig).filter(ServerConfig.id == 1).first()
    if row is None:
        row = ServerConfig(
            id=1,
            gateway_port=None,
            gateway_host=None,
            gateway_enabled=None,
        )
        db.add(row)
    if body.gateway_enabled is not None:
        row.gateway_enabled = body.gateway_enabled
    if body.gateway_host is not None:
        row.gateway_host = body.gateway_host
    if body.gateway_port is not None:
        row.gateway_port = body.gateway_port
    db.commit()
    db.refresh(row)

    cfg = get_effective_gateway_config(db)

    gateway = getattr(request.app.state, "gateway", None)
    gateway_task = getattr(request.app.state, "gateway_task", None)
    if gateway:
        await gateway.stop()
        if gateway_task:
            gateway_task.cancel()
            try:
                await gateway_task
            except asyncio.CancelledError:
                pass
    request.app.state.gateway = None
    request.app.state.gateway_task = None

    if cfg.enabled:
        from gateway import DetecGateway
        from protocol.connection import BaseConnection

        ssl_ctx = None
        if settings.gateway_tls_cert and settings.gateway_tls_key:
            ssl_ctx = BaseConnection.make_server_ssl_context(
                settings.gateway_tls_cert,
                settings.gateway_tls_key,
            )
        new_gateway = DetecGateway(
            host=cfg.host,
            port=cfg.port,
            ssl_context=ssl_ctx,
        )
        new_task = asyncio.create_task(new_gateway.serve())
        request.app.state.gateway = new_gateway
        request.app.state.gateway_task = new_task
        logger.info("Gateway listening on %s:%s", cfg.host, cfg.port)

    return ServerGatewaySettingsResponse(
        gateway_enabled=cfg.enabled,
        gateway_host=cfg.host,
        gateway_port=cfg.port,
    )
