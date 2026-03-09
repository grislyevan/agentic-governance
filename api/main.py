"""Agentic Governance — FastAPI backend.

Startup sequence:
  1. Create all tables (Alembic migrations in production)
  2. Seed default admin + tenant if DB is empty
  3. Launch staleness monitor
  4. Mount routers

Run dev server:
  cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

OpenAPI docs: http://localhost:8000/docs
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from sqlalchemy import text as sa_text

from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal, engine
from models import Tenant, User
from models.user import generate_api_key
from models.audit import AuditLog
from models.endpoint import Endpoint
from models.event import Event
from models.policy import Policy
from routers import audit, auth, endpoints, events, policies, users

logger = logging.getLogger("agentic_governance")

STALENESS_CHECK_INTERVAL = 60  # seconds


async def _staleness_monitor() -> None:
    """Periodic task that updates endpoint status based on heartbeat timing.

    Runs every STALENESS_CHECK_INTERVAL seconds.  When an endpoint
    transitions from active to stale/ungoverned, the status column is
    persisted so the dashboard and status API reflect the change.
    """
    while True:
        await asyncio.sleep(STALENESS_CHECK_INTERVAL)
        db = SessionLocal()
        try:
            all_endpoints = db.query(Endpoint).all()
            for ep in all_endpoints:
                new_status = ep.compute_status()
                if new_status != ep.status:
                    old = ep.status
                    ep.status = new_status
                    logger.info(
                        "Endpoint %s (%s) status %s -> %s",
                        ep.hostname, ep.id, old, new_status,
                    )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Staleness monitor cycle failed", exc_info=True)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _create_tables()
    _seed()
    monitor_task = asyncio.create_task(_staleness_monitor())
    yield
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


def _create_tables() -> None:
    """Ensure all tables exist.

    In production, run ``alembic upgrade head`` before starting the API
    so the schema is versioned.  create_all is kept as a dev convenience;
    it is a no-op when the tables already exist.
    """
    from core.database import Base
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def _seed() -> None:
    """Seed a default admin user and tenant on first startup."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.seed_admin_email).first()
        if existing:
            return

        slug = settings.seed_tenant_name.lower().replace(" ", "-")[:64]
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=settings.seed_tenant_name,
            slug=slug,
        )
        db.add(tenant)
        db.flush()

        raw_key, prefix, key_hash = generate_api_key()
        admin = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            first_name="Admin",
            role="owner",
            api_key_prefix=prefix,
            api_key_hash=key_hash,
        )
        db.add(admin)
        db.commit()
        logger.info("Seed: created tenant '%s' and admin '%s'", tenant.name, admin.email)
        logger.info(
            "[seed] Admin API key (save this, it will not be shown again): %s",
            raw_key,
        )
    except Exception:
        db.rollback()
        logger.warning("Seed skipped (set DEBUG=true for details)")
        logger.debug("Seed error details", exc_info=True)
    finally:
        db.close()


limiter = Limiter(key_func=get_remote_address)

_docs_kwargs: dict[str, Any] = {}
if not settings.debug:
    _docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}

app = FastAPI(
    title="Agentic Governance API",
    description="Endpoint telemetry and policy engine for agentic AI tool governance",
    version="0.1.0",
    lifespan=lifespan,
    **_docs_kwargs,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
)

app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(events.router)
app.include_router(endpoints.router)
app.include_router(policies.router)
app.include_router(users.router)


@app.get("/health", tags=["meta"])
def health() -> JSONResponse:
    db_ok = True
    try:
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
    except Exception:
        db_ok = False

    if db_ok:
        return JSONResponse({"status": "ok", "version": app.version, "db": "ok"})
    return JSONResponse(
        {"status": "degraded", "version": app.version, "db": "unreachable"},
        status_code=503,
    )
