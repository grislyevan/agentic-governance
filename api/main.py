"""Detec API entry point.

Startup sequence: bootstrap (migrations, seed), background tasks, gateway.
Run: cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000
OpenAPI: http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from core.logging_config import configure_logging
from core.config import settings
from core.database import SessionLocal

from core.rate_limit import limiter  # re-export for tests
from startup.app_factory import create_app
from startup import bootstrap
from startup import background_tasks


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.app_start_time = time.monotonic()
    configure_logging()
    bootstrap.apply_migrations()
    bootstrap.seed()
    db = SessionLocal()
    try:
        from core.retention import purge_expired_events
        purge_expired_events(db)
    except Exception:
        import logging
        logging.getLogger("agentic_governance").warning(
            "Startup retention purge failed", exc_info=True
        )
    finally:
        db.close()

    monitor_task = asyncio.create_task(background_tasks.staleness_monitor())
    purge_task = asyncio.create_task(background_tasks.retention_purge_loop())

    if settings.edr_enforcement_configured:
        from integrations.crowdstrike import CrowdStrikeProvider
        from integrations.crowdstrike_enforcement import CrowdStrikeEnforcementProvider
        from integrations import enforcement_router as enf_router

        cs_provider = CrowdStrikeProvider(
            api_base=settings.edr_api_base,
            client_id=settings.edr_client_id,
            client_secret=settings.edr_client_secret,
        )
        enf_router.register_provider(CrowdStrikeEnforcementProvider(cs_provider))

    gateway = None
    gateway_task = None
    db = SessionLocal()
    try:
        from core.server_config import get_effective_gateway_config
        gw_cfg = get_effective_gateway_config(db)
    finally:
        db.close()
    if gw_cfg.enabled:
        from gateway import DetecGateway
        from protocol.connection import BaseConnection

        ssl_ctx = None
        if settings.gateway_tls_cert and settings.gateway_tls_key:
            ssl_ctx = BaseConnection.make_server_ssl_context(
                settings.gateway_tls_cert,
                settings.gateway_tls_key,
            )

        gateway = DetecGateway(
            host=gw_cfg.host,
            port=gw_cfg.port,
            ssl_context=ssl_ctx,
        )
        gateway_task = asyncio.create_task(gateway.serve())
        app.state.gateway = gateway
        app.state.gateway_task = gateway_task

    yield

    if gateway:
        await gateway.stop()
    if gateway_task:
        gateway_task.cancel()
        try:
            await gateway_task
        except asyncio.CancelledError:
            pass

    purge_task.cancel()
    try:
        await purge_task
    except asyncio.CancelledError:
        pass
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


app = create_app(lifespan)
