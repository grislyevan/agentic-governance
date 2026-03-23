"""Tests for policies router: CRUD operations."""

from __future__ import annotations

from tests.conftest import API, _auth_header, login_user, register_user


def _auth(client):
    tokens = register_user(client, "pol@test.com", tenant_name="Pol Org")
    return _auth_header(tokens["access_token"])


def _minimal_event_body(event_id="from-ev-1"):
    return {
        "event_id": event_id,
        "event_type": "detection.observed",
        "event_version": "0.4.0",
        "observed_at": "2026-03-01T12:00:00Z",
        "tool": {"name": "Cursor", "class": "C", "version": "1.0"},
        "policy": {"decision_state": "detect", "rule_id": "ENFORCE-002"},
    }


class TestCreatePolicy:
    def test_create_returns_201(self, client):
        headers = _auth(client)
        resp = client.post(f"{API}/policies", json={
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
        resp = client.post(f"{API}/policies", json={"rule_id": "FAIL"})
        assert resp.status_code == 401


class TestCreatePolicyFromEvent:
    def test_from_event_returns_201_and_block_policy(self, client):
        headers = _auth(client)
        ingest = client.post(f"{API}/events", json=_minimal_event_body(), headers=headers)
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]
        resp = client.post(
            f"{API}/policies/from-event",
            json={"event_id": event_id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["rule_id"].startswith("CUSTOM-BLOCK-")
        assert data["parameters"]["decision_state"] == "block"
        assert data["category"] == "overlay"
        assert data["is_baseline"] is False
        assert "Cursor" in (data.get("description") or "")

    def test_from_event_404_for_unknown_event_id(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/policies/from-event",
            json={"event_id": "00000000-0000-0000-0000-000000000000"},
            headers=headers,
        )
        assert resp.status_code == 404

    def test_from_event_403_for_analyst(self, client):
        from core.database import get_db
        from models.user import User

        register_user(client, "fromev-owner@test.com", tenant_name="FromEv Org")
        owner_headers = _auth_header(login_user(client, "fromev-owner@test.com")["access_token"])
        ingest = client.post(f"{API}/events", json=_minimal_event_body("fe-2"), headers=owner_headers)
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]

        db = next(get_db())
        user = db.query(User).filter(User.email == "fromev-owner@test.com").first()
        user.role = "analyst"
        db.commit()

        analyst_headers = _auth_header(login_user(client, "fromev-owner@test.com")["access_token"])
        resp = client.post(
            f"{API}/policies/from-event",
            json={"event_id": event_id},
            headers=analyst_headers,
        )
        assert resp.status_code == 403


class TestListPolicies:
    def test_list_returns_tenant_policies(self, client):
        headers = _auth(client)
        client.post(f"{API}/policies", json={"rule_id": "R-1"}, headers=headers)
        client.post(f"{API}/policies", json={"rule_id": "R-2"}, headers=headers)
        resp = client.get(f"{API}/policies", headers=headers)
        assert resp.status_code == 200
        rules = [p["rule_id"] for p in resp.json()["items"]]
        assert "R-1" in rules
        assert "R-2" in rules


class TestUpdatePolicy:
    def test_patch_updates_fields(self, client):
        headers = _auth(client)
        created = client.post(f"{API}/policies", json={
            "rule_id": "UP-1", "description": "original",
        }, headers=headers).json()

        resp = client.patch(f"{API}/policies/{created['id']}", json={
            "rule_id": "UP-1",
            "description": "updated",
            "parameters": {"changed": True},
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"
        assert resp.json()["parameters"]["changed"] is True

    def test_patch_toggle_is_active(self, client):
        headers = _auth(client)
        created = client.post(f"{API}/policies", json={
            "rule_id": "TOGGLE-1",
        }, headers=headers).json()
        assert created["is_active"] is True

        resp = client.patch(f"{API}/policies/{created['id']}", json={
            "is_active": False,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False
        assert resp.json()["rule_id"] == "TOGGLE-1"

    def test_patch_nonexistent_returns_404(self, client):
        headers = _auth(client)
        resp = client.patch(f"{API}/policies/no-such-id", json={
            "rule_id": "X",
        }, headers=headers)
        assert resp.status_code == 404


class TestPolicyPresets:
    def test_list_presets_returns_all(self, client):
        headers = _auth(client)
        resp = client.get(f"{API}/policies/presets", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "presets" in data
        presets = data["presets"]
        assert len(presets) >= 4
        ids = {p["id"] for p in presets}
        assert "block_all_ai_coding" in ids
        assert "audit_only" in ids
        assert "allow_local_block_cloud" in ids
        assert "high_security" in ids
        for p in presets:
            assert "id" in p and "name" in p and "description" in p

    def test_list_presets_requires_auth(self, client):
        resp = client.get(f"{API}/policies/presets")
        assert resp.status_code == 401

    def test_apply_preset_updates_baseline_policies(self, client):
        headers = _auth(client)
        client.post(f"{API}/policies/restore-defaults", headers=headers)
        resp = client.post(
            f"{API}/policies/apply-preset",
            json={"preset_id": "audit_only"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["applied"] >= 1
        assert "audit_only" in data["message"].lower() or "applied" in data["message"].lower()

        list_resp = client.get(f"{API}/policies", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        # Audit-only preset downgrades block/approval_required to warn; at least one such rule should be warn
        warn_count = sum(
            1 for p in items
            if p.get("parameters", {}).get("decision_state") == "warn"
        )
        assert warn_count >= 1, "audit_only preset should set some rules to warn"

    def test_apply_preset_owner_succeeds(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/policies/apply-preset",
            json={"preset_id": "high_security"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["applied"] >= 0

    def test_apply_preset_unauthenticated_returns_401(self, client):
        resp = client.post(
            f"{API}/policies/apply-preset",
            json={"preset_id": "audit_only"},
        )
        assert resp.status_code == 401

    def test_apply_preset_unknown_id_returns_400(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/policies/apply-preset",
            json={"preset_id": "nonexistent_preset"},
            headers=headers,
        )
        assert resp.status_code == 400
