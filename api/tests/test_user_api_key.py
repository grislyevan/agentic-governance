"""Tests for current-user API key status and rotate endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.conftest import API, register_user


def test_get_my_api_key_after_register(client: TestClient) -> None:
    register_user(client, email="keyuser@test.com", password="testpass12345")
    r = client.get(f"{API}/users/me/api-key")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["configured"] is True
    assert data["prefix_display"] and len(data["prefix_display"]) >= 9


def test_rotate_my_api_key(client: TestClient) -> None:
    register_user(client, email="rotuser@test.com", password="testpass12345")
    before = client.get(f"{API}/users/me/api-key").json()["prefix_display"]
    r = client.post(f"{API}/users/me/api-key/rotate", json={})
    assert r.status_code == 200, r.text
    key = r.json()["api_key"]
    assert len(key) >= 32
    after = client.get(f"{API}/users/me/api-key").json()
    assert after["prefix_display"] != before
    assert after["prefix_display"].startswith(key[:8])
