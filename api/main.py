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
import os
import sys
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# PyInstaller bundles data files under sys._MEIPASS; in development,
# paths are relative to this file's location.
_BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from sqlalchemy import text as sa_text

from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal, engine
from models import Tenant, User
from models.user import API_KEY_PREFIX_LEN, generate_api_key, hash_api_key
from models.audit import AuditLog
from models.endpoint import Endpoint
from models.event import Event
from models.policy import Policy
from routers import agent_download, audit, auth, endpoints, enforcement, events, policies, users, webhooks

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
    _apply_migrations()
    _seed()
    monitor_task = asyncio.create_task(_staleness_monitor())

    gateway = None
    gateway_task = None
    if settings.gateway_enabled:
        from gateway import DetecGateway
        from protocol.connection import BaseConnection

        ssl_ctx = None
        if settings.gateway_tls_cert and settings.gateway_tls_key:
            ssl_ctx = BaseConnection.make_server_ssl_context(
                settings.gateway_tls_cert,
                settings.gateway_tls_key,
            )

        gateway = DetecGateway(
            host=settings.gateway_host,
            port=settings.gateway_port,
            ssl_context=ssl_ctx,
        )
        gateway_task = asyncio.create_task(gateway.serve())
        app.state.gateway = gateway

    yield

    if gateway:
        await gateway.stop()
    if gateway_task:
        gateway_task.cancel()
        try:
            await gateway_task
        except asyncio.CancelledError:
            pass

    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass


def _apply_migrations() -> None:
    """Run Alembic migrations on startup, falling back to create_all.

    For on-prem/single-binary deployments, this ensures the database
    schema is always up-to-date without requiring operators to run a
    separate ``alembic upgrade head`` command.
    """
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        ini_path = _BUNDLE_DIR / "alembic.ini"
        if ini_path.exists():
            cfg = AlembicConfig(str(ini_path))
            cfg.set_main_option("sqlalchemy.url", settings.database_url)
            alembic_command.upgrade(cfg, "head")
            logger.info("Alembic migrations applied successfully")
            return
    except Exception:
        logger.warning(
            "Alembic migration failed; falling back to create_all",
            exc_info=True,
        )

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

        from models.tenant import generate_agent_key

        slug = settings.seed_tenant_name.lower().replace(" ", "-")[:64]
        agent_key = settings.seed_agent_key or generate_agent_key()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=settings.seed_tenant_name,
            slug=slug,
            agent_key=agent_key,
        )
        db.add(tenant)
        db.flush()

        if settings.seed_api_key:
            raw_key = settings.seed_api_key
            prefix = raw_key[:API_KEY_PREFIX_LEN]
            key_hash = hash_api_key(raw_key)
        else:
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
        db.flush()

        from core.baseline_policies import seed_baseline_policies

        n_policies = seed_baseline_policies(db, tenant.id)
        db.commit()
        logger.info(
            "Seed: created tenant '%s', admin '%s', and %d baseline policies",
            tenant.name, admin.email, n_policies,
        )
        env = os.getenv("ENV", "development").lower()
        if env in ("production", "staging"):
            logger.info(
                "[seed] Admin API key prefix (full key written to seed-credentials.txt): %s...",
                raw_key[:8],
            )
            logger.info(
                "[seed] Tenant agent key prefix: %s...",
                agent_key[:8],
            )
            cred_path = Path("seed-credentials.txt")
            cred_path.write_text(
                f"admin_api_key={raw_key}\nagent_key={agent_key}\n",
                encoding="utf-8",
            )
            cred_path.chmod(0o600)
        else:
            logger.info(
                "[seed] Admin API key (save this, it will not be shown again): %s",
                raw_key,
            )
            logger.info(
                "[seed] Tenant agent key (used in agent packages): %s",
                agent_key,
            )
    except Exception:
        db.rollback()
        logger.warning("Seed skipped (set DEBUG=true for details)")
        logger.debug("Seed error details", exc_info=True)
    finally:
        db.close()


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["300/minute"],
    enabled=not os.environ.get("TESTING"),
)

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


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    env = os.getenv("ENV", "development").lower()
    if env in ("production", "staging"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
    return response


API_PREFIX = "/api"

app.include_router(agent_download.router, prefix=API_PREFIX)
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(events.router, prefix=API_PREFIX)
app.include_router(endpoints.router, prefix=API_PREFIX)
app.include_router(policies.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(webhooks.router, prefix=API_PREFIX)
app.include_router(enforcement.router, prefix=API_PREFIX)


@app.get("/health", tags=["meta"])
@app.get(f"{API_PREFIX}/health", tags=["meta"], include_in_schema=False)
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


# ---------------------------------------------------------------------------
# Static dashboard serving
# ---------------------------------------------------------------------------
# When dashboard/dist/ exists (built React app), serve it at the root.
# API routes take priority because they are registered first.
# ---------------------------------------------------------------------------

# In a PyInstaller bundle, dashboard is at _MEIPASS/dashboard/dist.
# In development, it's at <repo>/dashboard/dist (two levels up from api/).
_dashboard_dist = _BUNDLE_DIR / "dashboard" / "dist"
if not _dashboard_dist.is_dir():
    _dashboard_dist = Path(__file__).resolve().parent.parent / "dashboard" / "dist"

if _dashboard_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dashboard_dist / "assets"), name="dashboard-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_spa(full_path: str) -> FileResponse:
        """Serve the React SPA. Non-asset paths return index.html for client-side routing."""
        file_path = _dashboard_dist / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_dashboard_dist / "index.html")
