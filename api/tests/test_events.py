"""Tests for events router: ingest and query."""

from __future__ import annotations

from tests.conftest import API, _auth_header, register_user, login_user


def _auth(client):
    tokens = register_user(client, "evt@test.com", tenant_name="Evt Org")
    return _auth_header(tokens["access_token"])


def _event_body(event_id: str = "evt-001", **overrides) -> dict:
    base = {
        "event_id": event_id,
        "event_type": "detection",
        "event_version": "1.0",
        "observed_at": "2026-03-01T12:00:00Z",
        "tool": {"name": "Ollama", "class": "B", "version": "0.5.0"},
        "policy": {"decision_state": "detect", "rule_id": "RULE-001"},
        "severity": {"level": "P3"},
    }
    base.update(overrides)
    return base


class TestIngestEvent:
    def test_ingest_returns_201(self, client):
        headers = _auth(client)
        resp = client.post(f"{API}/events", json=_event_body(), headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == "evt-001"
        assert data["tool_name"] == "Ollama"
        assert data["tool_class"] == "B"
        assert data["decision_state"] == "detect"

    def test_ingest_duplicate_is_idempotent(self, client):
        headers = _auth(client)
        client.post(f"{API}/events", json=_event_body("dup-1"), headers=headers)
        resp = client.post(f"{API}/events", json=_event_body("dup-1"), headers=headers)
        assert resp.status_code == 200 or resp.status_code == 201

    def test_ingest_auto_creates_endpoint(self, client):
        headers = _auth(client)
        body = _event_body("ep-evt", endpoint={"hostname": "auto-ep", "os": "linux"})
        resp = client.post(f"{API}/events", json=body, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["event_id"] == "ep-evt"

    def test_ingest_unauthenticated_returns_401(self, client):
        resp = client.post(f"{API}/events", json=_event_body("no-auth"))
        assert resp.status_code == 401


class TestListEvents:
    def test_list_returns_ingested_events(self, client):
        headers = _auth(client)
        client.post(f"{API}/events", json=_event_body("list-1"), headers=headers)
        client.post(f"{API}/events", json=_event_body("list-2"), headers=headers)
        resp = client.get(f"{API}/events", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        ids = [e["event_id"] for e in data["items"]]
        assert "list-1" in ids
        assert "list-2" in ids

    def test_list_filter_by_tool_name(self, client):
        headers = _auth(client)
        client.post(
            f"{API}/events",
            json=_event_body("f-1", tool={"name": "Cursor"}),
            headers=headers,
        )
        client.post(
            f"{API}/events",
            json=_event_body("f-2", tool={"name": "Ollama"}),
            headers=headers,
        )
        resp = client.get(f"{API}/events?tool_name=Cursor", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(e["tool_name"] == "Cursor" for e in items)

    def test_list_pagination(self, client):
        headers = _auth(client)
        for i in range(5):
            client.post(f"{API}/events", json=_event_body(f"pg-{i}"), headers=headers)
        resp = client.get(f"{API}/events?page=1&page_size=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) == 2
        assert data["total"] >= 5

    def test_list_filter_by_mitre_technique(self, client):
        headers = _auth(client)
        body_with_mitre = _event_body(
            "mitre-1",
            mitre_attack={
                "techniques": [
                    {
                        "technique_id": "T1059",
                        "technique_name": "Command and Scripting Interpreter",
                        "tactic": "Execution",
                    }
                ]
            },
        )
        body_without_mitre = _event_body("mitre-2")
        client.post(f"{API}/events", json=body_with_mitre, headers=headers)
        client.post(f"{API}/events", json=body_without_mitre, headers=headers)
        resp = client.get(f"{API}/events?mitre_technique=T1059", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(
            any(
                t.get("technique_id") == "T1059"
                for t in (
                    e.get("payload", {}).get("mitre_attack", {}).get("techniques") or []
                )
            )
            for e in items
        )


class TestGetEvent:
    def test_get_event_by_id_returns_200(self, client):
        headers = _auth(client)
        ingest = client.post(
            f"{API}/events", json=_event_body("get-ev-1"), headers=headers
        )
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]
        resp = client.get(f"{API}/events/{event_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["event_id"] == "get-ev-1"
        assert resp.json()["id"] == event_id

    def test_get_event_404_for_unknown_id(self, client):
        headers = _auth(client)
        resp = client.get(
            f"{API}/events/00000000-0000-0000-0000-000000000000", headers=headers
        )
        assert resp.status_code == 404


class TestBlockEvent:
    def test_block_event_returns_200_and_creates_admin_block_event(self, client):
        headers = _auth(client)
        ingest = client.post(
            f"{API}/events", json=_event_body("block-ev-1"), headers=headers
        )
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]
        resp = client.post(f"{API}/events/{event_id}/block", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["event_id"] == event_id

        list_resp = client.get(f"{API}/events", headers=headers)
        items = list_resp.json()["items"]
        admin_blocks = [
            e for e in items if e.get("event_type") == "enforcement.admin_block"
        ]
        assert len(admin_blocks) >= 1

    def test_block_event_403_for_analyst(self, client):
        from core.database import get_db
        from models.user import User

        register_user(client, "block-owner@test.com", tenant_name="Block Org")
        owner_headers = _auth_header(
            login_user(client, "block-owner@test.com")["access_token"]
        )
        ingest = client.post(
            f"{API}/events", json=_event_body("block-ev-2"), headers=owner_headers
        )
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]

        db = next(get_db())
        user = db.query(User).filter(User.email == "block-owner@test.com").first()
        user.role = "analyst"
        db.commit()

        analyst_headers = _auth_header(
            login_user(client, "block-owner@test.com")["access_token"]
        )
        resp = client.post(f"{API}/events/{event_id}/block", headers=analyst_headers)
        assert resp.status_code == 403

    def test_block_event_404_for_unknown_id(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/events/00000000-0000-0000-0000-000000000000/block", headers=headers
        )
        assert resp.status_code == 404

    def test_block_event_cross_tenant_owner_denied(self, client):
        owner_a = _auth_header(
            register_user(client, "owner-a-events@test.com", tenant_name="Events A")[
                "access_token"
            ]
        )
        owner_b_tokens = register_user(
            client, "owner-b-events@test.com", tenant_name="Events B"
        )
        owner_b = _auth_header(owner_b_tokens["access_token"])

        ingest = client.post(
            f"{API}/events", json=_event_body("x-tenant-block-1"), headers=owner_b
        )
        assert ingest.status_code in (200, 201)
        event_id = ingest.json()["id"]

        resp = client.post(f"{API}/events/{event_id}/block", headers=owner_a)
        # Strict tenant scope on mutation path should prevent cross-tenant block-by-ID.
        assert resp.status_code == 404
