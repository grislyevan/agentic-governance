"""Tests for session reports API: aggregation from detection events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tests.conftest import API, _auth_header, register_user


def _auth(client):
    tokens = register_user(client, "sessionreport@test.com", tenant_name="SessionReport Org")
    return _auth_header(tokens["access_token"])


def _detection_event(client, headers, event_id: str, tool_name: str, observed_at: str, endpoint_id: str | None = None):
    body = {
        "event_id": event_id,
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": observed_at,
        "tool": {"name": tool_name, "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": endpoint_id or "ep-1", "hostname": "test-host", "os": "Darwin"},
    }
    return client.post(f"{API}/events", json=body, headers=headers)


def test_session_reports_empty_without_events(client):
    """GET /session-reports returns empty list when no detection events."""
    headers = _auth(client)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["items"] == []


def test_session_reports_aggregates_same_tool_same_endpoint(client):
    """Consecutive detection.observed events for same tool/endpoint become one session."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    for i in range(3):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        r = _detection_event(client, headers, f"sr-{i}", "Claude Cowork", t, "ep-session-1")
        assert r.status_code in (200, 201)

    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert len(data["items"]) >= 1
    sessions = [s for s in data["items"] if s["tool"] == "Claude Cowork"]
    assert len(sessions) >= 1
    report = sessions[0]
    assert report["tool"] == "Claude Cowork"
    assert report["duration_seconds"] >= 0
    assert "risk_signals" in report
    assert "actions" in report
    assert report["actions_note"] is not None  # N/A when from detection-only


def test_risk_signals_from_payload(client):
    """Session report includes risk signals derived from action.type and mitre_attack."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "risk-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Cursor", "class": "C", "version": "0.1"},
        "action": {"type": "repo", "risk_class": "R3", "summary": "Repo modification"},
        "mitre_attack": {
            "techniques": [
                {"technique_id": "T1552", "technique_name": "Unsecured Credentials", "tactic": "Credential Access"},
            ]
        },
        "endpoint": {"id": "ep-risk", "hostname": "host", "os": "Darwin"},
    }
    client.post(f"{API}/events", json=body, headers=headers)

    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    report = next((s for s in items if s["tool"] == "Cursor"), None)
    assert report is not None
    assert "repo modification" in report["risk_signals"]
    assert "credential access" in report["risk_signals"]
