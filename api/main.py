"""Agentic Governance — FastAPI backend.

Startup sequence:
  1. Create all tables (Alembic migrations in production)
  2. Seed default admin + tenant if DB is empty
  3. Mount routers

Run dev server:
  cd api && uvicorn main:app --reload --host 0.0.0.0 --port 8000

OpenAPI docs: http://localhost:8000/docs
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal, engine
from models import Tenant, User
from models.audit import AuditLog
from models.endpoint import Endpoint
from models.event import Event
from models.policy import Policy
from routers import auth, endpoints, events, policies


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    _create_tables()
    _seed()
    yield


def _create_tables() -> None:
    from core.database import Base
    import models  # noqa: F401 — ensure all models are registered
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

        admin = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            full_name="Admin",
            role="admin",
            api_key=uuid.uuid4().hex,
        )
        db.add(admin)
        db.commit()
        print(f"[seed] Created tenant '{tenant.name}' and admin '{admin.email}'")
    except Exception as exc:
        db.rollback()
        print(f"[seed] Seed skipped: {exc}")
    finally:
        db.close()


app = FastAPI(
    title="Agentic Governance API",
    description="Endpoint telemetry and policy engine for agentic AI tool governance",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(events.router)
app.include_router(endpoints.router)
app.include_router(policies.router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
