"""Rate limiting validation: verify 429 when limits are exceeded."""

from __future__ import annotations

import uuid

from tests.conftest import API, _auth_header, register_user
from core.database import get_db
from core.auth import create_access_token, hash_password
from models.tenant import Tenant
from models.user import User


def _seed_user_via_db(email: str, password: str = "testpass12345") -> dict:
    """Create a user directly in DB (bypasses register endpoint and its rate limit)."""
    db = next(get_db())
    tenant = Tenant(id=str(uuid.uuid4()), name="RL", slug="rl")
    db.add(tenant)
    db.flush()
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=email,
        hashed_password=hash_password(password),
        first_name="R",
        last_name="L",
        role="owner",
        auth_provider="local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    tokens = {
        "access_token": create_access_token(user.id, tenant.id),
        "refresh_token": "",
        "token_type": "bearer",
    }
    return tokens


class TestLoginRateLimit:
    """POST /auth/login is limited to 5/minute per IP."""

    def test_sixth_login_attempt_returns_429(self, client_with_ratelimit):
        client = client_with_ratelimit
        _seed_user_via_db("ratelimit@test.com")
        for _ in range(5):
            client.post(
                f"{API}/auth/login",
                json={"email": "ratelimit@test.com", "password": "wrong"},
            )
        resp = client.post(
            f"{API}/auth/login",
            json={"email": "ratelimit@test.com", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "detail" in resp.json()
        assert "Too many" in resp.json()["detail"] or "429" in str(resp.json())


class TestRegisterRateLimit:
    """POST /auth/register is limited to 3/minute per IP."""

    def test_fourth_register_attempt_returns_429(self, client_with_ratelimit):
        client = client_with_ratelimit
        for i in range(3):
            client.post(
                f"{API}/auth/register",
                json={"email": f"r{i}@test.com", "password": "testpass12345"},
            )
        resp = client.post(
            f"{API}/auth/register",
            json={"email": "r4@test.com", "password": "testpass12345"},
        )
        assert resp.status_code == 429
        assert "detail" in resp.json()


class TestEventIngestRateLimit:
    """POST /api/events is limited to 120/minute per IP."""

    def test_event_ingest_rate_limit_eventually_returns_429(self, client_with_ratelimit):
        client = client_with_ratelimit
        tokens = _seed_user_via_db("evt@test.com")
        auth = _auth_header(tokens["access_token"])
        base = {
            "event_id": "evt-{i}",
            "event_type": "detection",
            "event_version": "1.0",
            "observed_at": "2026-03-01T12:00:00Z",
            "tool": {"name": "Ollama"},
        }
        for i in range(121):
            body = {**base, "event_id": f"evt-{i}"}
            resp = client.post(f"{API}/events", json=body, headers=auth)
            if resp.status_code == 429:
                assert "detail" in resp.json()
                return
        assert False, "Expected 429 before 121 requests (limit may be higher or disabled)"


class TestForgotPasswordRateLimit:
    """POST /auth/forgot-password is limited to 3/minute per IP."""

    def test_fourth_forgot_password_returns_429(self, client_with_ratelimit):
        client = client_with_ratelimit
        _seed_user_via_db("forgot@test.com")
        for _ in range(3):
            client.post(
                f"{API}/auth/forgot-password",
                json={"email": "forgot@test.com"},
            )
        resp = client.post(
            f"{API}/auth/forgot-password",
            json={"email": "forgot@test.com"},
        )
        assert resp.status_code == 429
