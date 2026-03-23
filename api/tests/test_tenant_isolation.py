"""Tests that verify multi-tenant data isolation.

Owner and admin roles see data across all tenants (read-only).
Analyst and viewer roles must only see their own tenant's data.
"""

from __future__ import annotations

from tests.conftest import API, _auth_header, register_user


def _setup_two_tenants(client):
    """Register two users in separate tenants, return their auth headers."""
    tokens_a = register_user(client, "alice@a.com", tenant_name="Tenant A")
    tokens_b = register_user(client, "bob@b.com", tenant_name="Tenant B")
    return (
        _auth_header(tokens_a["access_token"]),
        _auth_header(tokens_b["access_token"]),
    )


def _create_analyst(client, owner_headers, email, password="testpass12345"):
    """Create an analyst user via the owner's API, return login tokens."""
    client.post(f"{API}/users", json={
        "email": email,
        "password": password,
        "first_name": "Test",
        "last_name": "Analyst",
        "role": "analyst",
    }, headers=owner_headers)
    resp = client.post(f"{API}/auth/login", json={
        "email": email,
        "password": password,
    })
    assert resp.status_code == 200, resp.text
    return _auth_header(resp.json()["access_token"])


class TestOwnerCrossTenantVisibility:
    """Owners can see data across all tenants on read endpoints."""

    def test_owner_sees_all_tenant_endpoints(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        client.post(f"{API}/endpoints", json={"hostname": "ws-a"}, headers=auth_a)
        client.post(f"{API}/endpoints", json={"hostname": "ws-b"}, headers=auth_b)

        resp = client.get(f"{API}/endpoints", headers=auth_a)
        assert resp.status_code == 200
        names = [e["hostname"] for e in resp.json()["items"]]
        assert "ws-a" in names
        assert "ws-b" in names

    def test_owner_sees_all_tenant_events(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        client.post(f"{API}/events", json={
            "event_id": "evt-a-1", "event_type": "detection",
            "event_version": "1.0", "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Ollama"},
        }, headers=auth_a)
        client.post(f"{API}/events", json={
            "event_id": "evt-b-1", "event_type": "detection",
            "event_version": "1.0", "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Cursor"},
        }, headers=auth_b)

        resp = client.get(f"{API}/events", headers=auth_a)
        assert resp.status_code == 200
        ids = [e["event_id"] for e in resp.json()["items"]]
        assert "evt-a-1" in ids
        assert "evt-b-1" in ids

    def test_owner_sees_all_tenant_policies(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        client.post(f"{API}/policies", json={
            "rule_id": "RULE-A", "description": "A's rule",
        }, headers=auth_a)
        client.post(f"{API}/policies", json={
            "rule_id": "RULE-B", "description": "B's rule",
        }, headers=auth_b)

        resp = client.get(f"{API}/policies", headers=auth_a)
        assert resp.status_code == 200
        rules = [p["rule_id"] for p in resp.json()["items"]]
        assert "RULE-A" in rules
        assert "RULE-B" in rules

    def test_owner_can_get_other_tenant_endpoint_by_id(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        resp = client.post(f"{API}/endpoints", json={"hostname": "private-b"}, headers=auth_b)
        ep_id = resp.json()["id"]

        resp = client.get(f"{API}/endpoints/{ep_id}", headers=auth_a)
        assert resp.status_code == 200


class TestAnalystTenantIsolation:
    """Analyst-role users remain scoped to their own tenant."""

    def test_analyst_cannot_see_other_tenant_endpoints(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        analyst_a = _create_analyst(client, auth_a, "analyst-a@a.com")

        client.post(f"{API}/endpoints", json={"hostname": "ws-a"}, headers=auth_a)
        client.post(f"{API}/endpoints", json={"hostname": "ws-b"}, headers=auth_b)

        resp = client.get(f"{API}/endpoints", headers=analyst_a)
        assert resp.status_code == 200
        names = [e["hostname"] for e in resp.json()["items"]]
        assert "ws-a" in names
        assert "ws-b" not in names

    def test_analyst_cannot_see_other_tenant_events(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        analyst_a = _create_analyst(client, auth_a, "analyst-a@a.com")

        client.post(f"{API}/events", json={
            "event_id": "evt-a-1", "event_type": "detection",
            "event_version": "1.0", "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Ollama"},
        }, headers=auth_a)
        client.post(f"{API}/events", json={
            "event_id": "evt-b-1", "event_type": "detection",
            "event_version": "1.0", "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Cursor"},
        }, headers=auth_b)

        resp = client.get(f"{API}/events", headers=analyst_a)
        assert resp.status_code == 200
        ids = [e["event_id"] for e in resp.json()["items"]]
        assert "evt-a-1" in ids
        assert "evt-b-1" not in ids

    def test_analyst_cannot_get_other_tenant_endpoint_by_id(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        analyst_a = _create_analyst(client, auth_a, "analyst-a@a.com")

        resp = client.post(f"{API}/endpoints", json={"hostname": "private-b"}, headers=auth_b)
        ep_id = resp.json()["id"]

        resp = client.get(f"{API}/endpoints/{ep_id}", headers=analyst_a)
        assert resp.status_code == 404
