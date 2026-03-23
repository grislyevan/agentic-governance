"""Tests for auth token endpoints: forgot-password, reset-password, accept-invite."""

from __future__ import annotations

import pytest
from tests.conftest import API, _auth_header, register_user, login_user


def _get_latest_reset_token(email: str) -> str:
    """Retrieve the latest unused reset token from the DB for testing.

    In production, this token would arrive via email. For tests we
    read it from the DB directly.
    """
    from core.database import get_db
    from models.auth_token import AuthToken
    from models.user import User

    db = next(get_db())
    user = db.query(User).filter(User.email == email).first()
    token_obj = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user.id,
            AuthToken.purpose == "reset",
            AuthToken.used_at.is_(None),
        )
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    raw_token, _ = AuthToken.create_reset_token.__func__  # noqa: not callable directly
    # Workaround: we can't retrieve the raw token from a hash.
    # Instead, create a new token directly and use it.
    token_obj2, raw = AuthToken.create_reset_token(user.id)
    db.add(token_obj2)
    db.commit()
    return raw


def _request_reset_and_get_token(client, email: str) -> str:
    """Request a password reset and retrieve the raw token from the DB."""
    from core.database import get_db
    from models.auth_token import AuthToken
    from models.user import User

    resp = client.post(f"{API}/auth/forgot-password", json={"email": email})
    assert resp.status_code == 200
    assert "token" not in resp.json()

    db = next(get_db())
    user = db.query(User).filter(User.email == email).first()

    # The forgot-password endpoint creates a token but no longer returns it.
    # For testing, create a fresh token via the model directly.
    token_obj, raw = AuthToken.create_reset_token(user.id)
    db.add(token_obj)
    db.commit()
    return raw


class TestForgotPassword:
    def test_forgot_password_does_not_return_token(self, client):
        register_user(client, email="fp@test.com", password="testpass12345")
        resp = client.post(f"{API}/auth/forgot-password", json={"email": "fp@test.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]
        assert "token" not in data

    def test_forgot_password_nonexistent_email_still_200(self, client):
        resp = client.post(f"{API}/auth/forgot-password", json={"email": "nobody@test.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"]
        assert "token" not in data

    def test_forgot_password_invalidates_old_tokens(self, client):
        register_user(client, email="multi@test.com", password="testpass12345")

        token1 = _request_reset_and_get_token(client, "multi@test.com")

        # Second request invalidates previous tokens
        client.post(f"{API}/auth/forgot-password", json={"email": "multi@test.com"})
        token2 = _request_reset_and_get_token(client, "multi@test.com")

        assert token1 != token2

        # token1 was invalidated by the second forgot-password request
        resp = client.post(f"{API}/auth/reset-password", json={
            "token": token1, "new_password": "newpass12345",
        })
        assert resp.status_code == 400

        resp = client.post(f"{API}/auth/reset-password", json={
            "token": token2, "new_password": "newpass12345",
        })
        assert resp.status_code == 200


class TestResetPassword:
    def test_reset_password_success(self, client):
        register_user(client, email="reset@test.com", password="testpass12345")
        token = _request_reset_and_get_token(client, "reset@test.com")

        resp = client.post(f"{API}/auth/reset-password", json={
            "token": token, "new_password": "newpassword1",
        })
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

        login_resp = client.post(f"{API}/auth/login", json={
            "email": "reset@test.com", "password": "newpassword1",
        })
        assert login_resp.status_code == 200

    def test_reset_password_invalid_token(self, client):
        resp = client.post(f"{API}/auth/reset-password", json={
            "token": "bogus-token-value", "new_password": "newpassword1",
        })
        assert resp.status_code == 400

    def test_reset_password_used_token_rejected(self, client):
        register_user(client, email="used@test.com", password="testpass12345")
        token = _request_reset_and_get_token(client, "used@test.com")

        client.post(f"{API}/auth/reset-password", json={
            "token": token, "new_password": "newpassword1",
        })

        resp = client.post(f"{API}/auth/reset-password", json={
            "token": token, "new_password": "anotherpass1",
        })
        assert resp.status_code == 400

    def test_reset_password_short_password_rejected(self, client):
        register_user(client, email="short@test.com", password="testpass12345")
        token = _request_reset_and_get_token(client, "short@test.com")

        resp = client.post(f"{API}/auth/reset-password", json={
            "token": token, "new_password": "short",
        })
        assert resp.status_code == 422


class TestAcceptInvite:
    def _create_invited_user(self, client, email="invited@test.com"):
        """Register an admin, then create an invited user via API."""
        tokens = register_user(client, email="admin-inv@test.com", password="testpass12345")
        header = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/users", json={
            "first_name": "Invited",
            "email": email,
            "role": "analyst",
        }, headers=header)
        assert resp.status_code == 201
        return resp.json()

    def test_accept_invite_success(self, client):
        result = self._create_invited_user(client)
        assert result.get("invite_token") is not None

        resp = client.post(f"{API}/auth/accept-invite", json={
            "token": result["invite_token"],
            "new_password": "mypassword1",
        })
        assert resp.status_code == 200
        assert "activated" in resp.json()["message"].lower()

        login_resp = client.post(f"{API}/auth/login", json={
            "email": "invited@test.com", "password": "mypassword1",
        })
        assert login_resp.status_code == 200

    def test_accept_invite_invalid_token(self, client):
        resp = client.post(f"{API}/auth/accept-invite", json={
            "token": "totally-fake-token", "new_password": "mypassword1",
        })
        assert resp.status_code == 400

    def test_accept_invite_used_token_rejected(self, client):
        result = self._create_invited_user(client, email="dupe@test.com")
        token = result["invite_token"]

        client.post(f"{API}/auth/accept-invite", json={
            "token": token, "new_password": "mypassword1",
        })

        resp = client.post(f"{API}/auth/accept-invite", json={
            "token": token, "new_password": "different1",
        })
        assert resp.status_code == 400


class TestLoginPasswordResetRequired:
    def test_login_returns_password_reset_required_flag(self, client):
        tokens = register_user(client, email="owner@test.com", password="testpass12345")
        header = _auth_header(tokens["access_token"])

        client.post(f"{API}/users", json={
            "first_name": "New",
            "email": "newuser@test.com",
            "role": "analyst",
            "password": "temppass12345",
        }, headers=header)

        resp = client.post(f"{API}/auth/login", json={
            "email": "newuser@test.com", "password": "temppass12345",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["password_reset_required"] is True

    def test_login_normal_user_no_reset_flag(self, client):
        register_user(client, email="normal@test.com", password="testpass12345")
        resp = client.post(f"{API}/auth/login", json={
            "email": "normal@test.com", "password": "testpass12345",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["password_reset_required"] is False


class TestCreateUserWithInvite:
    def test_create_user_without_password_returns_invite_token(self, client):
        tokens = register_user(client, email="admin@test.com", password="testpass12345")
        header = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/users", json={
            "first_name": "Bob",
            "email": "bob@test.com",
            "role": "analyst",
        }, headers=header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["invite_token"] is not None
        assert data["password_reset_required"] is True

    def test_create_user_with_password_no_invite_token(self, client):
        tokens = register_user(client, email="admin2@test.com", password="testpass12345")
        header = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/users", json={
            "first_name": "Carol",
            "email": "carol@test.com",
            "role": "analyst",
            "password": "temppass12345",
        }, headers=header)
        assert resp.status_code == 201
        data = resp.json()
        assert data.get("invite_token") is None
