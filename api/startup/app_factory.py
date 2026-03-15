"""FastAPI app factory: app creation, middleware, routers, health, static."""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text as sa_text

from core.logging_config import request_id_var
from core.metrics import (
    get_metrics,
    http_request_duration_seconds,
    http_requests_total,
)
from core.rate_limit import limiter
from core.config import settings
from core.database import SessionLocal
from models.event import Event

from routers import (
    agent_download,
    audit,
    auth,
    billing,
    data_flow,
    demo,
    endpoint_profiles,
    endpoints,
    enforcement,
    events,
    policies,
    reports,
    response_playbooks,
    retention,
    server_settings,
    session_reports,
    tenants,
    users,
    webhooks,
)

import logging

logger = logging.getLogger("agentic_governance")

API_PREFIX = "/api"
HEALTH_CHECK_TIMEOUT = 2.0
SKIP_LOG_PATHS = {"/health", "/api/health", "/metrics"}

_API_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
_ROOT_DIR = _API_DIR.parent
_dashboard_dist = _API_DIR / "dashboard" / "dist"
if not _dashboard_dist.is_dir():
    _dashboard_dist = _ROOT_DIR / "dashboard" / "dist"


def _apply_security_headers(response: Response) -> None:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    env = os.getenv("ENV", "development").lower()
    if env in ("production", "staging"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )


def _health_check_db() -> tuple[bool, str]:
    try:
        db = SessionLocal()
        db.execute(sa_text("SELECT 1"))
        db.close()
        return True, "ok"
    except Exception:
        return False, "unreachable"


def _health_check_gateway(request: Request) -> tuple[bool, str]:
    gateway = getattr(request.app.state, "gateway", None)
    if not gateway:
        return True, "disabled"
    if gateway.is_running():
        return True, "running"
    return False, "stopped"


def _health_last_event_at() -> str | None:
    try:
        from sqlalchemy import desc
        db = SessionLocal()
        try:
            row = (
                db.query(Event.observed_at)
                .order_by(desc(Event.observed_at))
                .limit(1)
                .first()
            )
            if row:
                return row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0])
        finally:
            db.close()
    except Exception:
        pass
    return None


def create_app(lifespan_context_manager):
    """Build the FastAPI app with middleware, routers, health, and static serving."""
    _docs_kwargs: dict[str, Any] = {}
    if not settings.debug:
        _docs_kwargs = {"docs_url": None, "redoc_url": None, "openapi_url": None}

    app = FastAPI(
        title="Detec API",
        description="Endpoint telemetry and policy engine for agentic AI tool governance",
        version="0.2.0",
        lifespan=lifespan_context_manager,
        **_docs_kwargs,
    )
    app.state.limiter = limiter

    async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        r = JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
        )
        _apply_security_headers(r)
        return r

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        r = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
        _apply_security_headers(r)
        return r

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
    )

    @app.middleware("http")
    async def request_logging_and_metrics(request: Request, call_next):
        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        path = request.url.path
        method = request.method
        client_ip = request.client.host if request.client else "unknown"
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            duration_ms = (time.perf_counter() - start) * 1000
            http_requests_total.labels(method=method, path=path, status=str(status)).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(
                duration_ms / 1000.0
            )
            if path not in SKIP_LOG_PATHS:
                logger.info(
                    "%s %s %s %d %.2fms",
                    method, path, client_ip, status, duration_ms,
                    extra={"request_id": request_id},
                )
            request_id_var.reset(token)
            return response
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            http_requests_total.labels(method=method, path=path, status=str(status)).inc()
            http_request_duration_seconds.labels(method=method, path=path).observe(
                duration_ms / 1000.0
            )
            if path not in SKIP_LOG_PATHS:
                logger.info(
                    "%s %s %s %d %.2fms",
                    method, path, client_ip, status, duration_ms,
                    extra={"request_id": request_id},
                )
            request_id_var.reset(token)
            raise

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        _apply_security_headers(response)
        return response

    app.include_router(agent_download.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(audit.router, prefix=API_PREFIX)
    app.include_router(events.router, prefix=API_PREFIX)
    app.include_router(retention.router, prefix=API_PREFIX)
    app.include_router(endpoints.router, prefix=API_PREFIX)
    app.include_router(endpoint_profiles.router, prefix=API_PREFIX)
    app.include_router(policies.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(webhooks.router, prefix=API_PREFIX)
    app.include_router(enforcement.router, prefix=API_PREFIX)
    app.include_router(billing.router, prefix=API_PREFIX)
    app.include_router(reports.router, prefix=API_PREFIX)
    app.include_router(session_reports.router, prefix=API_PREFIX)
    app.include_router(response_playbooks.router, prefix=API_PREFIX)
    app.include_router(server_settings.router, prefix=API_PREFIX)
    app.include_router(data_flow.router, prefix=API_PREFIX)
    app.include_router(tenants.router, prefix=API_PREFIX)
    app.include_router(demo.router, prefix=API_PREFIX)

    @app.get("/metrics", tags=["meta"], include_in_schema=False)
    def metrics() -> Response:
        return Response(
            content=get_metrics(),
            media_type="text/plain; charset=utf-8",
        )

    @app.get("/health", tags=["meta"])
    @app.get(f"{API_PREFIX}/health", tags=["meta"], include_in_schema=False)
    async def health(request: Request) -> JSONResponse:
        components: dict[str, Any] = {}
        critical_fail = False
        degraded = False

        try:
            db_ok, db_status = await asyncio.wait_for(
                asyncio.to_thread(_health_check_db),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            db_ok, db_status = False, "timeout"
        components["database"] = db_status
        if not db_ok:
            critical_fail = True

        gw_ok, gw_status = _health_check_gateway(request)
        components["gateway"] = gw_status
        if not gw_ok and getattr(request.app.state, "gateway", None) is not None:
            degraded = True

        try:
            last_event = await asyncio.wait_for(
                asyncio.to_thread(_health_last_event_at),
                timeout=HEALTH_CHECK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            last_event = None
        components["last_event_at"] = last_event

        app_start = getattr(request.app.state, "app_start_time", None)
        uptime = int(time.monotonic() - app_start) if app_start is not None else 0
        components["uptime_seconds"] = uptime

        if critical_fail:
            overall = "unhealthy"
            status_code = 503
        elif degraded:
            overall = "degraded"
            status_code = 503
        else:
            overall = "healthy"
            status_code = 200

        return JSONResponse(
            {
                "status": overall,
                "version": app.version,
                "components": components,
            },
            status_code=status_code,
        )

    if _dashboard_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=_dashboard_dist / "assets"), name="dashboard-assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def _serve_spa(full_path: str) -> FileResponse:
            file_path = _dashboard_dist / full_path
            if full_path and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(_dashboard_dist / "index.html")

    return app
