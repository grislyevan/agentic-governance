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


def test_session_report_includes_timeline_when_in_payload(client):
    """When detection event has session_timeline, GET session-reports returns it on the report."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "timeline-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Cursor", "class": "C", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-timeline", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash npm install", "type": "shell_exec"},
            {"at": "13:04:11", "label": "write package.json", "type": "file_write"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)

    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    report = next((s for s in items if s["tool"] == "Cursor" and s.get("session_timeline")), None)
    assert report is not None
    assert "session_timeline" in report
    timeline = report["session_timeline"]
    assert len(timeline) == 3
    assert timeline[0]["at"] == "13:04:02" and timeline[0]["label"] == "LLM request"
    assert timeline[1]["label"] == "bash npm install"
    assert timeline[2]["label"] == "write package.json"


def test_session_report_timeline_process_attribution_and_summary(client):
    """Session report includes process_name, pid, parent_pid and timeline_summary when in payload."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "timeline-enrich-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "TimelineEnrichTool", "class": "C", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-enrich", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:05", "label": "bash npm install", "type": "shell_exec", "pid": 4423, "parent_pid": 100, "parent_process_name": "cursor", "process_name": "bash"},
            {"at": "13:04:14", "label": "git commit", "type": "git"},
        ],
        "timeline_summary": {"llm": 0, "shell_exec": 1, "file_write": 0, "git": 1},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)

    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    report = next(
        (s for s in items if s["tool"] == "TimelineEnrichTool" and s.get("session_timeline")),
        None,
    )
    assert report is not None
    assert report.get("timeline_summary") == {"llm": 0, "shell_exec": 1, "file_write": 0, "git": 1}
    timeline = report["session_timeline"]
    assert len(timeline) == 2
    assert timeline[0].get("pid") == 4423
    assert timeline[0].get("parent_pid") == 100
    assert timeline[0].get("parent_process_name") == "cursor"
    assert timeline[0].get("process_name") == "bash"


def test_session_risk_from_max_risk_class(client):
    """Session report session_risk is max of action.risk_class in session (R1=0.25 .. R4=1.0)."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    for i, risk in enumerate(["R1", "R3"]):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        body = {
            "event_id": f"risk-max-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": {"name": "ScoreTool", "class": "B", "version": "0.1"},
            "action": {"type": "exec", "risk_class": risk, "summary": "Tool detected"},
            "endpoint": {"id": "ep-score", "hostname": "host", "os": "Darwin"},
        }
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "ScoreTool"), None)
    assert report is not None
    assert report.get("session_risk") == 0.75  # max of R1 (0.25) and R3 (0.75)


def test_session_confidence_from_max_attribution(client):
    """Session report session_confidence is max tool.attribution_confidence across events."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    for i, conf in enumerate([0.6, 0.9]):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        body = {
            "event_id": f"conf-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": {"name": "ConfTool", "class": "B", "version": "0.1", "attribution_confidence": conf},
            "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
            "endpoint": {"id": "ep-conf", "hostname": "host", "os": "Darwin"},
        }
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "ConfTool"), None)
    assert report is not None
    assert report.get("session_confidence") == 0.9


def test_top_risk_signals_ordered_by_count(client):
    """Session report top_risk_signals is ordered by frequency across events."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    # Three events: two with exec (shell execution), one with repo (repo modification)
    for i in range(3):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        action_type = "exec" if i < 2 else "repo"
        body = {
            "event_id": f"top-sig-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": {"name": "TopSigTool", "class": "B", "version": "0.1"},
            "action": {"type": action_type, "risk_class": "R2", "summary": "Detected"},
            "endpoint": {"id": "ep-topsig", "hostname": "host", "os": "Darwin"},
        }
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "TopSigTool"), None)
    assert report is not None
    top = report.get("top_risk_signals") or []
    # shell execution appears 2x, repo modification 1x
    assert "shell execution" in top
    assert "repo modification" in top
    assert top.index("shell execution") < top.index("repo modification")


def test_top_behavior_chains_from_timeline(client):
    """Session report top_behavior_chains derived from consecutive session_timeline types."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "chain-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "ChainTool", "class": "C", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-chain", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash npm install", "type": "shell_exec"},
            {"at": "13:04:11", "label": "write package.json", "type": "file_write"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "ChainTool" and s.get("session_timeline")), None)
    assert report is not None
    chains = report.get("top_behavior_chains") or []
    assert "llm_call -> shell_exec" in chains
    assert "shell_exec -> file_write" in chains


def test_session_scoring_none_when_no_data(client):
    """session_risk and session_confidence are None when payloads lack risk_class/attribution_confidence."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "no-score-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "NoScoreTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "summary": "Tool detected"},
        "endpoint": {"id": "ep-noscore", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "NoScoreTool"), None)
    assert report is not None
    assert report.get("session_risk") is None
    assert report.get("session_confidence") is None


def test_top_behavior_chains_none_without_timeline(client):
    """top_behavior_chains is None when session has no session_timeline."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "no-timeline-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "NoTimelineTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-notl", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "NoTimelineTool"), None)
    assert report is not None
    assert report.get("session_timeline") is None
    assert report.get("top_behavior_chains") is None
