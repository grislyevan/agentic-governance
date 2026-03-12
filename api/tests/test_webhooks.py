"""Tests for webhook CRUD endpoints and dispatcher logic."""

from __future__ import annotations

import json

import pytest
from tests.conftest import API, _auth_header, register_user


def _setup_admin(client):
    tokens = register_user(client, email="whadmin@test.com", password="testpass12345")
    return _auth_header(tokens["access_token"])


class TestWebhookCRUD:
    def test_create_webhook(self, client):
        header = _setup_admin(client)
        resp = client.post(f"{API}/webhooks", json={
            "url": "https://example.com/hook",
            "events": ["enforcement.block"],
        }, headers=header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["url"] == "https://example.com/hook"
        assert data["events"] == ["enforcement.block"]
        assert data["is_active"] is True
        assert data["secret"].startswith("whsec_")
        assert data["id"]

    def test_create_webhook_all_events(self, client):
        header = _setup_admin(client)
        resp = client.post(f"{API}/webhooks", json={
            "url": "https://example.com/all",
            "events": [],
        }, headers=header)
        assert resp.status_code == 201
        assert resp.json()["events"] == []

    def test_list_webhooks(self, client):
        header = _setup_admin(client)
        client.post(f"{API}/webhooks", json={
            "url": "https://example.com/a",
            "events": [],
        }, headers=header)
        client.post(f"{API}/webhooks", json={
            "url": "https://example.com/b",
            "events": ["enforcement.warn"],
        }, headers=header)

        resp = client.get(f"{API}/webhooks", headers=header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_update_webhook(self, client):
        header = _setup_admin(client)
        create_resp = client.post(f"{API}/webhooks", json={
            "url": "https://example.com/orig",
            "events": [],
        }, headers=header)
        wh_id = create_resp.json()["id"]

        resp = client.patch(f"{API}/webhooks/{wh_id}", json={
            "url": "https://example.com/updated",
            "is_active": False,
        }, headers=header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["url"] == "https://example.com/updated"
        assert data["is_active"] is False

    def test_delete_webhook(self, client):
        header = _setup_admin(client)
        create_resp = client.post(f"{API}/webhooks", json={
            "url": "https://example.com/delete-me",
            "events": [],
        }, headers=header)
        wh_id = create_resp.json()["id"]

        resp = client.delete(f"{API}/webhooks/{wh_id}", headers=header)
        assert resp.status_code == 204

        list_resp = client.get(f"{API}/webhooks", headers=header)
        assert list_resp.json()["total"] == 0

    def test_delete_nonexistent_webhook(self, client):
        header = _setup_admin(client)
        resp = client.delete(f"{API}/webhooks/fake-id-123", headers=header)
        assert resp.status_code == 404


class TestWebhookValidation:
    def test_create_webhook_invalid_url(self, client):
        header = _setup_admin(client)
        resp = client.post(f"{API}/webhooks", json={
            "url": "not-a-url",
            "events": [],
        }, headers=header)
        assert resp.status_code == 422

    def test_create_webhook_requires_auth(self, client):
        resp = client.post(f"{API}/webhooks", json={
            "url": "https://example.com/noauth",
            "events": [],
        })
        assert resp.status_code == 401

    def test_webhook_requires_admin_role(self, client):
        admin_header = _setup_admin(client)

        client.post(f"{API}/users", json={
            "first_name": "Viewer",
            "email": "viewer@test.com",
            "role": "viewer",
            "password": "viewerpass1",
        }, headers=admin_header)

        login_resp = client.post(f"{API}/auth/login", json={
            "email": "viewer@test.com", "password": "viewerpass1",
        })
        viewer_header = _auth_header(login_resp.json()["access_token"])

        resp = client.get(f"{API}/webhooks", headers=viewer_header)
        assert resp.status_code == 403


class TestWebhookDispatcher:
    def test_dispatcher_matches_all_events(self, client):
        from webhooks.dispatcher import _matches
        assert _matches("[]", None, "block") is True
        assert _matches("[]", None, None) is True

    def test_dispatcher_matches_decision_state(self, client):
        from webhooks.dispatcher import _matches
        events = json.dumps(["block", "warn"])
        assert _matches(events, None, "block") is True
        assert _matches(events, None, "allow") is False

    def test_dispatcher_matches_event_type(self, client):
        from webhooks.dispatcher import _matches
        events = json.dumps(["enforcement.applied", "enforcement.failed"])
        assert _matches(events, "enforcement.applied", "block") is True
        assert _matches(events, "posture.changed", None) is False

    def test_dispatcher_no_match_on_wrong_event(self, client):
        from webhooks.dispatcher import _matches
        events = json.dumps(["block"])
        assert _matches(events, None, "allow") is False

    def test_build_payload(self, client):
        from webhooks.dispatcher import _build_payload
        event_data = {
            "event_id": "evt-123",
            "event_type": "tool.detection",
            "observed_at": "2026-03-10T12:00:00Z",
            "tool": {"name": "cursor", "class": "ide", "version": "1.0"},
            "policy": {"decision_state": "allow", "rule_id": "r1"},
            "severity": {"level": "info"},
            "endpoint": {"hostname": "mac-01"},
        }
        payload = _build_payload(event_data, "tenant-abc")
        assert payload["event_id"] == "evt-123"
        assert payload["tenant_id"] == "tenant-abc"
        assert payload["tool"]["name"] == "cursor"
        assert payload["policy"]["decision_state"] == "allow"
        assert payload["endpoint"]["hostname"] == "mac-01"

    def test_build_payload_includes_enforcement_and_posture(self, client):
        from webhooks.dispatcher import _build_payload
        event_data = {
            "event_id": "evt-456",
            "event_type": "enforcement.applied",
            "observed_at": "2026-03-11T03:14:22Z",
            "tool": {"name": "Unknown Agent", "class": "C", "attribution_confidence": 0.82},
            "policy": {"decision_state": "block", "rule_id": "ENFORCE-004"},
            "severity": {"level": "S3"},
            "endpoint": {"hostname": "prod-db-01", "posture": "active"},
            "enforcement": {
                "tactic": "process_kill",
                "success": True,
                "pids_killed": [12345, 12346, 12347],
                "process_name": "python3",
                "cmdline_snippet": "python3 agent.py --target prod-db",
                "rate_limited": False,
                "simulated": False,
                "allow_listed": False,
                "provider": "local",
            },
        }
        payload = _build_payload(event_data, "tenant-xyz")
        assert payload["event_type"] == "enforcement.applied"
        assert payload["tool"]["attribution_confidence"] == 0.82
        assert payload["endpoint"]["posture"] == "active"
        assert payload["enforcement"]["tactic"] == "process_kill"
        assert payload["enforcement"]["success"] is True
        assert payload["enforcement"]["pids_killed"] == [12345, 12346, 12347]


class TestWebhookSender:
    def test_sign_payload(self, client):
        from webhooks.sender import _sign_payload
        payload = b'{"test": true}'
        sig = _sign_payload(payload, "secret123")
        assert len(sig) == 64

        sig2 = _sign_payload(payload, "secret123")
        assert sig == sig2

        sig3 = _sign_payload(payload, "different")
        assert sig3 != sig
