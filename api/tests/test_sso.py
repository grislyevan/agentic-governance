"""Tests for SSO/OIDC authentication."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

import jwt as pyjwt

from tests.conftest import API, _auth_header
from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal
from models.tenant import Tenant
from models.user import User


class TestSsoStatus:
    def test_sso_status_returns_configured_false_when_oidc_not_set(self, client):
        resp = client.get(f"{API}/auth/sso/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["configured"] is False

    def test_sso_status_returns_configured_true_when_oidc_set(self):
        with patch.dict(
            os.environ,
            {
                "OIDC_ISSUER": "https://idp.example.com",
                "OIDC_CLIENT_ID": "test-client",
                "OIDC_CLIENT_SECRET": "test-secret",
            },
            clear=False,
        ):
            from core.config import Settings
            settings = Settings()
            assert settings.oidc_configured is True


class TestSsoLogin:
    def test_sso_login_returns_503_when_oidc_not_configured(self, client):
        resp = client.get(f"{API}/auth/sso/login", follow_redirects=False)
        assert resp.status_code == 503
        data = resp.json()
        assert "not configured" in data["detail"].lower()


class TestLocalLoginGuard:
    def test_local_login_blocked_for_oidc_user(self, client):
        db = SessionLocal()
        try:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Test",
                slug="test-oidc",
            )
            db.add(tenant)
            db.flush()
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email="oidc@test.com",
                hashed_password=hash_password("unused"),
                role="analyst",
                auth_provider="oidc",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"{API}/auth/login",
            json={"email": "oidc@test.com", "password": "anypassword"},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "SSO" in data["detail"]
        assert "identity provider" in data["detail"]


class TestSsoPasswordReset:
    def test_sso_user_cannot_use_password_reset(self, client):
        db = SessionLocal()
        try:
            tenant = Tenant(
                id=str(uuid.uuid4()),
                name="Test",
                slug="test-oidc-reset",
            )
            db.add(tenant)
            db.flush()
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email="oidc-reset@test.com",
                hashed_password=hash_password("unused"),
                role="analyst",
                auth_provider="oidc",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        resp = client.post(
            f"{API}/auth/forgot-password",
            json={"email": "oidc-reset@test.com"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reset" in data["message"].lower()
        assert "registered" in data["message"].lower()


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("authlib") is None,
    reason="authlib required for SSO callback tests",
)
class TestSsoCallback:
    def test_sso_callback_returns_503_when_not_configured(self, client):
        resp = client.post(
            f"{API}/auth/sso/callback",
            json={"code": "fake-code", "state": "fake-state"},
        )
        assert resp.status_code == 503, resp.text

    def test_sso_callback_rejects_invalid_state(self, client):
        mock_settings = MagicMock()
        mock_settings.oidc_configured = True
        mock_settings.oidc_redirect_uri = "http://localhost:5173/auth/sso/callback"
        with patch("core.config.settings", mock_settings):
            resp = client.post(
                f"{API}/auth/sso/callback",
                json={"code": "fake-code", "state": "invalid-state"},
            )
        assert resp.status_code == 400
        data = resp.json()
        assert "state" in data["detail"].lower()

    def test_sso_callback_creates_new_user_with_auth_provider_oidc(self, client):
        nonce = "test-nonce-123"
        state_jwt = pyjwt.encode(
            {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.jwt_secret,
            algorithm="HS256",
        )
        id_token_claims = {
            "sub": "oidc-sub-123",
            "email": "newoidc@test.com",
            "nonce": nonce,
            "aud": "test-client",
            "iss": "https://idp.example.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
        }
        mock_token = {
            "id_token": "fake",
            "access_token": "fake",
            "userinfo": {"email": "newoidc@test.com", "given_name": "New", "family_name": "User"},
        }
        mock_metadata = {
            "token_endpoint": "https://idp.example.com/token",
            "jwks_uri": "https://idp.example.com/jwks",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }

        mock_settings = MagicMock()
        mock_settings.oidc_configured = True
        mock_settings.oidc_redirect_uri = "http://localhost:5173/auth/sso/callback"
        mock_settings.oidc_client_id = "test-client"
        mock_settings.oidc_issuer = "https://idp.example.com"
        with patch("core.config.settings", mock_settings), \
             patch("authlib.integrations.httpx_client.OAuth2Client") as mock_oauth_cls, \
             patch("httpx.Client") as mock_client_cls:
            mock_oauth = MagicMock()
            mock_oauth.fetch_token.return_value = mock_token
            mock_oauth_cls.return_value = mock_oauth

            def make_resp(data):
                r = MagicMock()
                r.json.return_value = data
                r.raise_for_status = MagicMock()
                return r

            mock_http = MagicMock()
            mock_http.get.side_effect = lambda url: make_resp(
                mock_metadata if "openid-configuration" in url else {"keys": []}
            )
            mock_http.__enter__ = MagicMock(return_value=mock_http)
            mock_http.__exit__ = MagicMock(return_value=False)
            mock_client_cls.return_value = mock_http

            with patch("jwt.decode", side_effect=[{"nonce": nonce}, id_token_claims]):
                resp = client.post(
                    f"{API}/auth/sso/callback",
                    json={"code": "fake-code", "state": state_jwt},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "newoidc@test.com").first()
            assert user is not None
            assert user.auth_provider == "oidc"
        finally:
            db.close()

    def test_sso_callback_logs_in_existing_oidc_user(self, client):
        db = SessionLocal()
        try:
            tenant = Tenant(id=str(uuid.uuid4()), name="Existing", slug="existing-oidc")
            db.add(tenant)
            db.flush()
            user = User(
                id=str(uuid.uuid4()),
                tenant_id=tenant.id,
                email="existing-oidc@test.com",
                hashed_password=hash_password("unused"),
                role="analyst",
                auth_provider="oidc",
            )
            db.add(user)
            db.commit()
        finally:
            db.close()

        nonce = "test-nonce-456"
        state_jwt = pyjwt.encode(
            {"nonce": nonce, "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            settings.jwt_secret,
            algorithm="HS256",
        )
        id_token_claims = {
            "sub": "oidc-sub-456",
            "email": "existing-oidc@test.com",
            "nonce": nonce,
            "aud": "test-client",
            "iss": "https://idp.example.com",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
        }
        mock_token = {
            "id_token": "fake",
            "access_token": "fake",
            "userinfo": {"email": "existing-oidc@test.com"},
        }

        mock_metadata = {
            "token_endpoint": "https://idp.example.com/token",
            "jwks_uri": "https://idp.example.com/jwks",
        }

        def make_resp(data):
            r = MagicMock()
            r.json.return_value = data
            r.raise_for_status = MagicMock()
            return r

        mock_http = MagicMock()
        mock_http.get.side_effect = lambda url: make_resp(
            mock_metadata if "openid-configuration" in url else {"keys": []}
        )
        mock_http.__enter__ = MagicMock(return_value=mock_http)
        mock_http.__exit__ = MagicMock(return_value=False)

        mock_settings = MagicMock()
        mock_settings.oidc_configured = True
        mock_settings.oidc_redirect_uri = "http://localhost:5173/auth/sso/callback"
        mock_settings.oidc_issuer = "https://idp.example.com"
        mock_settings.oidc_client_id = "test-client"
        with patch("core.config.settings", mock_settings), \
             patch("authlib.integrations.httpx_client.OAuth2Client") as mock_oauth_cls, \
             patch("httpx.Client", return_value=mock_http):
            mock_oauth = MagicMock()
            mock_oauth.fetch_token.return_value = mock_token
            mock_oauth_cls.return_value = mock_oauth

            with patch("jwt.decode", side_effect=[{"nonce": nonce}, id_token_claims]):
                resp = client.post(
                    f"{API}/auth/sso/callback",
                    json={"code": "fake-code", "state": state_jwt},
                )

        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        me = client.get(f"{API}/auth/me", headers=_auth_header(data["access_token"]))
        assert me.status_code == 200
        assert me.json()["email"] == "existing-oidc@test.com"
