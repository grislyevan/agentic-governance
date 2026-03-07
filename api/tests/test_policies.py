"""Tests for policies router: CRUD operations."""

from __future__ import annotations

from tests.conftest import _auth_header, register_user


def _auth(client):
    tokens = register_user(client, "pol@test.com", tenant_name="Pol Org")
    return _auth_header(tokens["access_token"])


class TestCreatePolicy:
    def test_create_returns_201(self, client):
        headers = _auth(client)
        resp = client.post("/policies", json={
            "rule_id": "GOV-001",
            "description": "Block Class D tools on Tier 1 assets",
            "parameters": {"tool_class": "D", "sensitivity": "Tier1"},
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_id"] == "GOV-001"
        assert data["is_active"] is True
        assert data["parameters"]["tool_class"] == "D"

    def test_create_unauthenticated_returns_401(self, client):
        resp = client.post("/policies", json={"rule_id": "FAIL"})
        assert resp.status_code == 401


class TestListPolicies:
    def test_list_returns_tenant_policies(self, client):
        headers = _auth(client)
        client.post("/policies", json={"rule_id": "R-1"}, headers=headers)
        client.post("/policies", json={"rule_id": "R-2"}, headers=headers)
        resp = client.get("/policies", headers=headers)
        assert resp.status_code == 200
        rules = [p["rule_id"] for p in resp.json()]
        assert "R-1" in rules
        assert "R-2" in rules


class TestUpdatePolicy:
    def test_patch_updates_fields(self, client):
        headers = _auth(client)
        created = client.post("/policies", json={
            "rule_id": "UP-1", "description": "original",
        }, headers=headers).json()

        resp = client.patch(f"/policies/{created['id']}", json={
            "rule_id": "UP-1",
            "description": "updated",
            "parameters": {"changed": True},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"
        assert resp.json()["parameters"]["changed"] is True

    def test_patch_nonexistent_returns_404(self, client):
        headers = _auth(client)
        resp = client.patch("/policies/no-such-id", json={
            "rule_id": "X",
        }, headers=headers)
        assert resp.status_code == 404
