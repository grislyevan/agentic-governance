"""Tests for events router: ingest and query."""

from __future__ import annotations

from tests.conftest import _auth_header, register_user


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
        resp = client.post("/events", json=_event_body(), headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["event_id"] == "evt-001"
        assert data["tool_name"] == "Ollama"
        assert data["tool_class"] == "B"
        assert data["decision_state"] == "detect"

    def test_ingest_duplicate_is_idempotent(self, client):
        headers = _auth(client)
        client.post("/events", json=_event_body("dup-1"), headers=headers)
        resp = client.post("/events", json=_event_body("dup-1"), headers=headers)
        assert resp.status_code == 200 or resp.status_code == 201

    def test_ingest_auto_creates_endpoint(self, client):
        headers = _auth(client)
        body = _event_body("ep-evt", endpoint={"hostname": "auto-ep", "os": "linux"})
        resp = client.post("/events", json=body, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["event_id"] == "ep-evt"

    def test_ingest_unauthenticated_returns_401(self, client):
        resp = client.post("/events", json=_event_body("no-auth"))
        assert resp.status_code == 401


class TestListEvents:
    def test_list_returns_ingested_events(self, client):
        headers = _auth(client)
        client.post("/events", json=_event_body("list-1"), headers=headers)
        client.post("/events", json=_event_body("list-2"), headers=headers)
        resp = client.get("/events", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        ids = [e["event_id"] for e in data["items"]]
        assert "list-1" in ids
        assert "list-2" in ids

    def test_list_filter_by_tool_name(self, client):
        headers = _auth(client)
        client.post("/events", json=_event_body("f-1", tool={"name": "Cursor"}), headers=headers)
        client.post("/events", json=_event_body("f-2", tool={"name": "Ollama"}), headers=headers)
        resp = client.get("/events?tool_name=Cursor", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert all(e["tool_name"] == "Cursor" for e in items)

    def test_list_pagination(self, client):
        headers = _auth(client)
        for i in range(5):
            client.post("/events", json=_event_body(f"pg-{i}"), headers=headers)
        resp = client.get("/events?page=1&page_size=2", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) == 2
        assert data["total"] >= 5
