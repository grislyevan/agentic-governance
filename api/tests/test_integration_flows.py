"""Multi-step integration tests for API flows.

Covers auth lifecycle, policy lifecycle, and event ingestion to query.
Uses SQLite in-memory (conftest) for CI compatibility.
"""

from __future__ import annotations

import uuid

from tests.conftest import API, _auth_header, register_user


def _canonical_event(event_id: str, event_type: str = "detection.observed", **overrides) -> dict:
    """Build a minimal canonical event payload."""
    base = {
        "event_id": event_id,
        "event_type": event_type,
        "event_version": "0.4.0",
        "observed_at": "2026-03-12T14:00:00.000Z",
        "session_id": "sess-int-001",
        "trace_id": "trace-int-001",
        "parent_event_id": None,
        "actor": {
            "id": "user@test.com",
            "type": "human",
            "trust_tier": "T1",
            "identity_confidence": 0.8,
            "org_context": "org",
        },
        "endpoint": {
            "id": "INT-TEST-HOST",
            "os": "macOS 26.3 Darwin 25.3.0 ARM64",
            "posture": "managed",
        },
        "tool": {
            "name": "Claude Code",
            "class": "C",
            "version": "2.1.59",
            "attribution_confidence": 0.77,
            "attribution_sources": ["process", "file"],
        },
        "action": {
            "type": "exec",
            "risk_class": "R2",
            "summary": "Integration test detection",
            "raw_ref": "evidence://test/int-001",
        },
        "target": {
            "type": "host",
            "id": "INT-TEST-HOST",
            "scope": "local endpoint",
            "sensitivity_tier": "Tier0",
        },
        "severity": {"level": "S1"},
    }
    base.update(overrides)
    return base


class TestAuthLifecycle:
    """Flow 1: Register, login, access protected endpoint, refresh, use new token."""

    def test_auth_lifecycle(self, client):
        reg = register_user(client, "authflow@test.com", tenant_name="Auth Flow Org")
        assert "access_token" in reg
        assert "refresh_token" in reg
        assert "api_key" in reg

        token = reg["access_token"]
        me = client.get(f"{API}/auth/me", headers=_auth_header(token))
        assert me.status_code == 200
        assert me.json()["email"] == "authflow@test.com"

        refresh_resp = client.post(
            f"{API}/auth/refresh",
            json={"refresh_token": reg["refresh_token"]},
        )
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data
        assert new_data["access_token"] != token

        me2 = client.get(f"{API}/auth/me", headers=_auth_header(new_data["access_token"]))
        assert me2.status_code == 200
        assert me2.json()["email"] == "authflow@test.com"


class TestPolicyLifecycle:
    """Flow 2: Login as admin, create policy, list, update, toggle, delete."""

    def test_policy_lifecycle(self, client):
        reg = register_user(client, "policyflow@test.com", tenant_name="Policy Flow Org")
        headers = _auth_header(reg["access_token"])

        create_resp = client.post(
            f"{API}/policies",
            json={
                "rule_id": "CUSTOM-INT-001",
                "rule_version": "0.4.0",
                "description": "Integration test policy",
                "is_active": True,
                "parameters": {"decision_state": "detect"},
            },
            headers=headers,
        )
        assert create_resp.status_code == 201
        policy = create_resp.json()
        policy_id = policy["id"]
        assert policy["rule_id"] == "CUSTOM-INT-001"
        assert policy["is_active"] is True

        list_resp = client.get(f"{API}/policies", headers=headers)
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        found = next((p for p in items if p["id"] == policy_id), None)
        assert found is not None
        assert found["rule_id"] == "CUSTOM-INT-001"

        update_resp = client.patch(
            f"{API}/policies/{policy_id}",
            json={"description": "Updated integration test policy"},
            headers=headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["description"] == "Updated integration test policy"

        toggle_resp = client.patch(
            f"{API}/policies/{policy_id}",
            json={"is_active": False},
            headers=headers,
        )
        assert toggle_resp.status_code == 200
        assert toggle_resp.json()["is_active"] is False

        delete_resp = client.delete(f"{API}/policies/{policy_id}", headers=headers)
        assert delete_resp.status_code == 204

        list_after = client.get(f"{API}/policies", headers=headers)
        assert list_after.status_code == 200
        remaining = [p for p in list_after.json()["items"] if p["id"] == policy_id]
        assert len(remaining) == 0


class TestEventIngestionToQuery:
    """Flow 3: Auth, POST event, GET events, filter by type, verify endpoint auto-registered."""

    def test_event_ingestion_to_query(self, client):
        reg = register_user(client, "eventflow@test.com", tenant_name="Event Flow Org")
        headers = _auth_header(reg["access_token"])

        event_id = f"int-{uuid.uuid4().hex[:12]}"
        body = _canonical_event(event_id, endpoint={"id": "AUTO-EP-001", "os": "Linux", "posture": "unmanaged"})
        post_resp = client.post(f"{API}/events", json=body, headers=headers)
        assert post_resp.status_code == 201
        assert post_resp.json()["event_id"] == event_id

        get_resp = client.get(f"{API}/events", headers=headers)
        assert get_resp.status_code == 200
        items = get_resp.json()["items"]
        found = next((e for e in items if e["event_id"] == event_id), None)
        assert found is not None
        assert found["tool_name"] == "Claude Code"

        filter_resp = client.get(
            f"{API}/events?event_type=detection.observed",
            headers=headers,
        )
        assert filter_resp.status_code == 200
        filtered = filter_resp.json()["items"]
        assert all(e["event_type"] == "detection.observed" for e in filtered)
        ids = [e["event_id"] for e in filtered]
        assert event_id in ids

        list_ep = client.get(f"{API}/endpoints", headers=headers)
        assert list_ep.status_code == 200
        endpoints = list_ep.json()["items"]
        ep_hosts = [e["hostname"] for e in endpoints]
        assert "AUTO-EP-001" in ep_hosts
