"""Shared test fixtures for the API test suite.

Uses an in-memory SQLite database so tests don't need PostgreSQL.
"""

from __future__ import annotations

import os
import sys
import uuid

# api/ must be importable as the root
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# Configure test environment BEFORE any app module is imported.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-jwt-secret-for-unit-tests-only"
os.environ["SEED_ADMIN_PASSWORD"] = "testpass12345"
os.environ["TESTING"] = "1"
os.environ["RATELIMIT_ENABLED"] = "false"
os.environ["GATEWAY_ENABLED"] = "false"
# Ensure OIDC is not configured for auth tests (override any .env)
for key in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_REDIRECT_URI"):
    os.environ[key] = ""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import core.database as _db_mod
from core.database import Base, get_db
from core.auth import create_access_token, hash_password

# Build a SQLite in-memory engine that all threads share.
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Patch the database module so every part of the app uses the test engine.
_db_mod.engine = _test_engine
_db_mod.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine,
)

# Register all ORM models with Base.metadata.
import models  # noqa: F401
from models.tenant import Tenant
from models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

API = "/api"


@pytest.fixture()
def client():
    """FastAPI TestClient backed by a fresh in-memory database."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    from main import app, limiter
    limiter.enabled = False

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def client_with_ratelimit():
    """TestClient with rate limiting enabled (for test_rate_limits.py)."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    from main import app, limiter
    limiter.enabled = True
    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    finally:
        limiter.enabled = False


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def register_user(
    client: TestClient,
    email: str = "alice@test.com",
    password: str = "testpass12345",
    tenant_name: str | None = None,
) -> dict:
    body: dict = {"email": email, "password": password}
    if tenant_name:
        body["tenant_name"] = tenant_name
    resp = client.post(f"{API}/auth/register", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def login_user(
    client: TestClient,
    email: str = "alice@test.com",
    password: str = "testpass12345",
) -> dict:
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()
