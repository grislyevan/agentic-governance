"""Auth cookie-based session: cookie flags, login/refresh/logout/me with cookies."""

from __future__ import annotations

import re

import pytest

from tests.conftest import API, login_user, register_user


def _set_cookie_headers(response) -> list[str]:
    try:
        return response.headers.get_list("set-cookie")
    except Exception:
        pass
    single = response.headers.get("set-cookie")
    return [single] if single else []


def _cookie_has_flags(set_cookie_value: str, *flags: str) -> bool:
    lower = set_cookie_value.lower()
    return all(f.lower() in lower for f in flags)


class TestLoginSetsCookies:
    """Login and register responses set httpOnly, sameSite cookies."""

    def test_login_sets_access_and_refresh_cookies(self, client):
        register_user(client, "cookie-login@test.com")
        resp = client.post(
            f"{API}/auth/login",
            json={"email": "cookie-login@test.com", "password": "testpass12345"},
        )
        assert resp.status_code == 200
        set_cookies = _set_cookie_headers(resp)
        assert len(set_cookies) >= 2
        access = [c for c in set_cookies if "detec_access_token" in c]
        refresh = [c for c in set_cookies if "detec_refresh_token" in c]
        assert len(access) == 1
        assert len(refresh) == 1
        assert _cookie_has_flags(access[0], "httponly", "samesite")
        assert _cookie_has_flags(refresh[0], "httponly", "samesite")

    def test_register_sets_cookies(self, client):
        resp = client.post(
            f"{API}/auth/register",
            json={
                "email": "cookie-reg@test.com",
                "password": "testpass12345",
                "tenant_name": "Cookie Org",
            },
        )
        assert resp.status_code == 201
        set_cookies = _set_cookie_headers(resp)
        assert len(set_cookies) >= 2
        assert any("detec_access_token" in c for c in set_cookies)
        assert any("detec_refresh_token" in c for c in set_cookies)


class TestMeWithCookie:
    """GET /auth/me works with cookie only (no Authorization header)."""

    def test_me_with_cookie_after_login(self, client):
        register_user(client, "me-cookie@test.com")
        client.post(
            f"{API}/auth/login",
            json={"email": "me-cookie@test.com", "password": "testpass12345"},
        )
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "me-cookie@test.com"


class TestRefreshWithCookie:
    """POST /auth/refresh accepts refresh token from cookie."""

    def test_refresh_with_cookie_only(self, client):
        register_user(client, "refresh-cookie@test.com")
        client.post(
            f"{API}/auth/login",
            json={"email": "refresh-cookie@test.com", "password": "testpass12345"},
        )
        resp = client.post(f"{API}/auth/refresh", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data


class TestLogoutClearsCookies:
    """POST /auth/logout clears session cookies."""

    def test_logout_returns_204_and_clears_cookies(self, client):
        register_user(client, "logout@test.com")
        client.post(
            f"{API}/auth/login",
            json={"email": "logout@test.com", "password": "testpass12345"},
        )
        resp = client.post(f"{API}/auth/logout")
        assert resp.status_code == 204
        set_cookies = _set_cookie_headers(resp)
        for h in set_cookies:
            if "detec_access_token" in h or "detec_refresh_token" in h:
                assert "max-age=0" in h or "expires=" in h.lower()

    def test_me_after_logout_returns_401(self, client):
        register_user(client, "after-logout@test.com")
        client.post(
            f"{API}/auth/login",
            json={"email": "after-logout@test.com", "password": "testpass12345"},
        )
        client.post(f"{API}/auth/logout")
        resp = client.get(f"{API}/auth/me")
        assert resp.status_code == 401
