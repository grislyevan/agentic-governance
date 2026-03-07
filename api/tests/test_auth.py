"""Tests for auth router: register, login, refresh, /me."""

from __future__ import annotations

from tests.conftest import _auth_header, login_user, register_user


class TestRegister:
    def test_register_creates_user_and_returns_tokens(self, client):
        data = register_user(client, "new@test.com")
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email_returns_409(self, client):
        register_user(client, "dup@test.com")
        resp = client.post("/auth/register", json={
            "email": "dup@test.com", "password": "testpass12345",
        })
        assert resp.status_code == 409

    def test_register_short_password_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "email": "short@test.com", "password": "abc",
        })
        assert resp.status_code == 422

    def test_register_invalid_email_returns_422(self, client):
        resp = client.post("/auth/register", json={
            "email": "not-an-email", "password": "testpass12345",
        })
        assert resp.status_code == 422

    def test_register_custom_tenant_name(self, client):
        tokens = register_user(client, "org@test.com", tenant_name="Acme Corp")
        me = client.get("/auth/me", headers=_auth_header(tokens["access_token"]))
        assert me.status_code == 200


class TestLogin:
    def test_login_returns_tokens(self, client):
        register_user(client, "login@test.com")
        data = login_user(client, "login@test.com")
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client):
        register_user(client, "wrong@test.com")
        resp = client.post("/auth/login", json={
            "email": "wrong@test.com", "password": "badpassword1",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_email(self, client):
        resp = client.post("/auth/login", json={
            "email": "ghost@test.com", "password": "testpass12345",
        })
        assert resp.status_code == 401


class TestRefresh:
    def test_refresh_returns_valid_tokens(self, client):
        tokens = register_user(client, "refresh@test.com")
        resp = client.post("/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        assert resp.status_code == 200
        new = resp.json()
        assert "access_token" in new
        assert "refresh_token" in new
        assert new["token_type"] == "bearer"

    def test_refresh_with_access_token_fails(self, client):
        tokens = register_user(client, "badref@test.com")
        resp = client.post("/auth/refresh", json={
            "refresh_token": tokens["access_token"],
        })
        assert resp.status_code == 401

    def test_refresh_with_garbage_token_fails(self, client):
        resp = client.post("/auth/refresh", json={
            "refresh_token": "not.a.real.token",
        })
        assert resp.status_code == 401


class TestMe:
    def test_me_returns_user_info(self, client):
        tokens = register_user(client, "me@test.com", tenant_name="My Org")
        resp = client.get("/auth/me", headers=_auth_header(tokens["access_token"]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@test.com"
        assert data["role"] == "admin"
        assert "tenant_id" in data

    def test_me_without_auth_returns_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401

    def test_me_with_bad_token_returns_401(self, client):
        resp = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
