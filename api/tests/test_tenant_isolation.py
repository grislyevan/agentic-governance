"""Tests that verify multi-tenant data isolation.

Each tenant must only see its own endpoints, events, and policies.
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


class TestEndpointIsolation:
    def test_tenant_a_cannot_see_tenant_b_endpoints(self, client):
        auth_a, auth_b = _setup_two_tenants(client)

        client.post(f"{API}/endpoints", json={"hostname": "ws-a"}, headers=auth_a)
        client.post(f"{API}/endpoints", json={"hostname": "ws-b"}, headers=auth_b)

        resp_a = client.get(f"{API}/endpoints", headers=auth_a)
        assert resp_a.status_code == 200
        names_a = [e["hostname"] for e in resp_a.json()["items"]]
        assert "ws-a" in names_a
        assert "ws-b" not in names_a

        resp_b = client.get(f"{API}/endpoints", headers=auth_b)
        names_b = [e["hostname"] for e in resp_b.json()["items"]]
        assert "ws-b" in names_b
        assert "ws-a" not in names_b

    def test_tenant_a_cannot_get_tenant_b_endpoint_by_id(self, client):
        auth_a, auth_b = _setup_two_tenants(client)

        resp = client.post(f"{API}/endpoints", json={"hostname": "private-b"}, headers=auth_b)
        ep_id = resp.json()["id"]

        resp = client.get(f"{API}/endpoints/{ep_id}", headers=auth_a)
        assert resp.status_code == 404


class TestEventIsolation:
    def test_tenant_a_cannot_see_tenant_b_events(self, client):
        auth_a, auth_b = _setup_two_tenants(client)

        client.post(f"{API}/events", json={
            "event_id": "evt-a-1",
            "event_type": "detection",
            "event_version": "1.0",
            "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Ollama"},
        }, headers=auth_a)

        client.post(f"{API}/events", json={
            "event_id": "evt-b-1",
            "event_type": "detection",
            "event_version": "1.0",
            "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Cursor"},
        }, headers=auth_b)

        resp_a = client.get(f"{API}/events", headers=auth_a)
        assert resp_a.status_code == 200
        ids_a = [e["event_id"] for e in resp_a.json()["items"]]
        assert "evt-a-1" in ids_a
        assert "evt-b-1" not in ids_a


class TestPolicyIsolation:
    def test_tenant_a_cannot_see_tenant_b_policies(self, client):
        auth_a, auth_b = _setup_two_tenants(client)

        client.post(f"{API}/policies", json={
            "rule_id": "RULE-A", "description": "A's rule",
        }, headers=auth_a)

        client.post(f"{API}/policies", json={
            "rule_id": "RULE-B", "description": "B's rule",
        }, headers=auth_b)

        resp_a = client.get(f"{API}/policies", headers=auth_a)
        assert resp_a.status_code == 200
        rules_a = [p["rule_id"] for p in resp_a.json()["items"]]
        assert "RULE-A" in rules_a
        assert "RULE-B" not in rules_a
