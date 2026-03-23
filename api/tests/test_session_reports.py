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
    assert "id" in report
    assert isinstance(report["id"], str) and len(report["id"]) > 0
    assert "session_report_id" in report
    assert report["session_report_id"] == report["id"]
    assert "started_at" in report and "endpoint_id" in report and "tool" in report
    assert "session_verdict" in report and "session_confidence" in report
    assert "timeline_summary" in report or "recommended_action" in report


def test_session_report_get_by_id(client):
    """GET /session-reports/{id} returns the report when id exists; 404 when not found."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    for i in range(2):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        _detection_event(client, headers, f"getbyid-{i}", "Aider", t, "ep-getbyid")

    list_resp = client.get(f"{API}/session-reports", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    aider = next((s for s in items if s["tool"] == "Aider"), None)
    assert aider is not None
    session_id = aider["id"]
    assert session_id

    get_resp = client.get(f"{API}/session-reports/{session_id}", headers=headers)
    assert get_resp.status_code == 200
    report = get_resp.json()
    assert report["id"] == session_id
    assert report["tool"] == "Aider"

    not_found = client.get(f"{API}/session-reports/nonexistent-id-12345", headers=headers)
    assert not_found.status_code == 404


def test_session_list_without_time_params_then_get_by_id_returns_200(client):
    """List with no since/before uses default 7-day window; any session in list is fetchable by id."""
    headers = _auth(client)
    base = datetime.now(timezone.utc)
    for i in range(2):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        _detection_event(client, headers, f"list-then-get-{i}", "Cursor", t, "ep-listget")

    list_resp = client.get(f"{API}/session-reports", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    cursor_sessions = [s for s in items if s["tool"] == "Cursor"]
    assert len(cursor_sessions) >= 1
    session_id = cursor_sessions[0]["session_report_id"] or cursor_sessions[0]["id"]
    assert session_id

    get_resp = client.get(f"{API}/session-reports/{session_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == session_id


def test_session_report_canned_demo_id_returns_demo(client):
    """GET /session-reports/demo-session-canned returns the canned demo session."""
    headers = _auth(client)
    resp = client.get(f"{API}/session-reports/demo-session-canned", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "demo-session-canned"
    assert data["tool"] == "Claude Code"
    assert data.get("session_timeline")


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


def test_session_report_includes_evasion_vectors_when_in_payload(client):
    """When detection event has agent_status.tamper_vectors or evidence_details.evasion_findings, report has evasion_vectors (E3-05)."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "evasion-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Evasion Detection", "class": "A", "version": "0.1"},
        "action": {"type": "observe", "risk_class": "R1", "summary": "Evasion indicators"},
        "agent_status": {"tamper_vectors": ["E1-global-hook", "capability_drift"]},
        "evidence_details": {
            "evasion_findings": [
                {"vector": "E1-global-hook", "description": "Global hook strips trailers", "path": "/hooks/commit-msg"},
            ]
        },
        "endpoint": {"id": "ep-evasion", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Evasion Detection"), None)
    assert report is not None
    assert "evasion_vectors" in report
    vectors = report["evasion_vectors"] or []
    assert "E1-global-hook" in vectors
    assert "capability_drift" in vectors


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
    # Use base in the past so both events are within the session lookback window (observed_at <= now at GET time).
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    tool_name = "ScoreToolRiskMax"
    for i, risk in enumerate(["R1", "R3"]):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        body = {
            "event_id": f"risk-max-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": {"name": tool_name, "class": "B", "version": "0.1"},
            "action": {"type": "exec", "risk_class": risk, "summary": "Tool detected"},
            "endpoint": {"id": "ep-score", "hostname": "host", "os": "Darwin"},
        }
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == tool_name), None)
    assert report is not None
    assert report.get("session_risk") == 0.75  # max of R1 (0.25) and R3 (0.75)


def test_session_confidence_robust_aggregate(client):
    """Session report session_confidence is mean of top-k attribution_confidence across events."""
    headers = _auth(client)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
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
    # Two events: top-2 mean of [0.6, 0.9] = 0.75
    assert report.get("session_confidence") == 0.75


def test_session_confidence_outlier_dampened(client):
    """Session confidence uses top-k mean so one high outlier does not dominate."""
    headers = _auth(client)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    confs = [0.5, 0.5, 0.95]
    for i, conf in enumerate(confs):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        body = {
            "event_id": f"outlier-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": {"name": "OutlierTool", "class": "B", "version": "0.1", "attribution_confidence": conf},
            "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
            "endpoint": {"id": "ep-outlier", "hostname": "host", "os": "Darwin"},
        }
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "OutlierTool"), None)
    assert report is not None
    # Top-3 mean of [0.95, 0.5, 0.5] = 0.65; closer to bulk (0.5) than to max (0.95)
    assert report.get("session_confidence") == 0.65


def test_top_risk_signals_ordered_by_count(client):
    """Session report top_risk_signals is ordered by frequency across events."""
    headers = _auth(client)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
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
    assert "llm -> shell_exec" in chains
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


def test_verdict_high_risk_session_yields_high_risk(client):
    """High risk session (session_risk >= 1.0) yields session_verdict high_risk."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "high-risk-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "HighRiskTool", "class": "B", "version": "0.1", "attribution_confidence": 0.8},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk action"},
        "endpoint": {"id": "ep-highrisk", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "HighRiskTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "high_risk"
    assert report.get("recommended_action") == "contain"
    reasons = report.get("verdict_reasons") or []
    assert any("R4" in r or "threshold" in r.lower() for r in reasons)


def test_verdict_moderate_risk_yields_risky(client):
    """Moderate risk (session_risk >= 0.75) yields session_verdict risky."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "risky-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "RiskyTool", "class": "B", "version": "0.1", "attribution_confidence": 0.7},
        "action": {"type": "exec", "risk_class": "R3", "summary": "Moderate risk"},
        "endpoint": {"id": "ep-risky", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "RiskyTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "risky"
    assert report.get("recommended_action") == "review"


def test_verdict_low_risk_with_behavior_chain_yields_interesting(client):
    """Low risk with behavior chain yields session_verdict interesting."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "interesting-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "InterestingTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-interesting", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "InterestingTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "interesting"
    assert report.get("recommended_action") == "review"
    reasons = report.get("verdict_reasons") or []
    assert any("chain" in r.lower() or "agentic" in r.lower() or "moderate" in r.lower() for r in reasons)


def test_verdict_beh001_only_no_escalation(client):
    """BEH-001 only (shell fan-out) without file_write/git keeps current verdict; no escalation."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh001-only-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh001OnlyTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-beh001-only", "hostname": "host", "os": "Darwin"},
        "evidence_details": {"detection_codes": ["DETEC-BEH-CORE-01"]},
        "session_timeline": [
            {"at": "13:04:02", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:08", "label": "network", "type": "network"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh001OnlyTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "interesting"
    reasons = report.get("verdict_reasons") or []
    assert not any("autonomous shell burst followed by repository modification" in r for r in reasons)


def test_verdict_beh001_plus_file_write_escalates_to_risky(client):
    """BEH-001 + file_write escalates verdict to risky with explicit reason."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh001-fw-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh001FileWriteTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-beh001-fw", "hostname": "host", "os": "Darwin"},
        "evidence_details": {"detection_codes": ["DETEC-BEH-CORE-01"]},
        "session_timeline": [
            {"at": "13:04:02", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:05", "label": "write package.json", "type": "file_write"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh001FileWriteTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "risky"
    assert report.get("recommended_action") == "review"
    reasons = report.get("verdict_reasons") or []
    assert any("autonomous shell burst followed by repository modification" in r for r in reasons)


def test_verdict_beh001_plus_git_escalates_to_risky(client):
    """BEH-001 + git activity escalates verdict to risky with explicit reason."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh001-git-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh001GitTool", "class": "B", "version": "0.1"},
        "action": {"type": "repo", "risk_class": "R2", "summary": "Repo modification"},
        "endpoint": {"id": "ep-beh001-git", "hostname": "host", "os": "Darwin"},
        "evidence_details": {"detection_codes": ["DETEC-BEH-CORE-01"]},
        "session_timeline": [
            {"at": "13:04:02", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:10", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh001GitTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "risky"
    assert report.get("recommended_action") == "review"
    reasons = report.get("verdict_reasons") or []
    assert any("autonomous shell burst followed by repository modification" in r for r in reasons)


def test_verdict_beh001_unrelated_activity_no_escalation(client):
    """BEH-001 with only unrelated activity (e.g. network) does not escalate."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh001-unrelated-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh001UnrelatedTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-beh001-unrelated", "hostname": "host", "os": "Darwin"},
        "evidence_details": {"detection_codes": ["DETEC-BEH-CORE-01"]},
        "session_timeline": [
            {"at": "13:04:02", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:05", "label": "outbound", "type": "network"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh001UnrelatedTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "interesting"
    reasons = report.get("verdict_reasons") or []
    assert not any("autonomous shell burst followed by repository modification" in r for r in reasons)


def test_beh009_normal_unchanged_without_broader_impact(client):
    """BEH-009 without broader-impact evidence: verdict/reasons unchanged (no multi-file/repeated-git)."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh009-normal-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh009NormalTool", "class": "C", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-beh009-n", "hostname": "host", "os": "Darwin"},
        "evidence_details": {
            "detection_codes": ["DETEC-BEH-CORE-04"],
            "behavioral_patterns": [
                {
                    "pattern_id": "BEH-009",
                    "pattern_name": "Agent Execution Chain",
                    "score": 0.8,
                    "evidence": {
                        "distinct_file_count": 1,
                        "git_action_count": 1,
                        "multi_file_change": False,
                        "repeated_git_activity": False,
                    },
                },
            ],
        },
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:11", "label": "write file", "type": "file_write"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh009NormalTool"), None)
    assert report is not None
    reasons = report.get("verdict_reasons") or []
    assert not any("touched multiple files" in r for r in reasons)
    assert not any("repeated git activity" in r for r in reasons)


def test_beh009_multi_file_adds_reason_and_evidence(client):
    """BEH-009 with multi_file_change True: verdict reasons and key_evidence mention multiple files."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh009-multi-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh009MultiFileTool", "class": "C", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-beh009-m", "hostname": "host", "os": "Darwin"},
        "evidence_details": {
            "detection_codes": ["DETEC-BEH-CORE-04"],
            "behavioral_patterns": [
                {
                    "pattern_id": "BEH-009",
                    "pattern_name": "Agent Execution Chain",
                    "score": 0.8,
                    "evidence": {
                        "distinct_file_count": 3,
                        "git_action_count": 0,
                        "multi_file_change": True,
                        "repeated_git_activity": False,
                    },
                },
            ],
        },
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:11", "label": "write a.py", "type": "file_write"},
            {"at": "13:04:12", "label": "write b.py", "type": "file_write"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh009MultiFileTool"), None)
    assert report is not None
    reasons = report.get("verdict_reasons") or []
    assert any("touched multiple files" in r for r in reasons)
    evidence = report.get("key_evidence") or []
    assert any("multiple files" in e for e in evidence)


def test_beh009_repeated_git_adds_reason_and_evidence(client):
    """BEH-009 with repeated_git_activity True: verdict reasons and key_evidence mention repeated git."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "beh009-git-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "Beh009RepeatedGitTool", "class": "C", "version": "0.1"},
        "action": {"type": "repo", "risk_class": "R2", "summary": "Repo"},
        "endpoint": {"id": "ep-beh009-g", "hostname": "host", "os": "Darwin"},
        "evidence_details": {
            "detection_codes": ["DETEC-BEH-CORE-04"],
            "behavioral_patterns": [
                {
                    "pattern_id": "BEH-009",
                    "pattern_name": "Agent Execution Chain",
                    "score": 0.8,
                    "evidence": {
                        "distinct_file_count": 1,
                        "git_action_count": 3,
                        "multi_file_change": False,
                        "repeated_git_activity": True,
                    },
                },
            ],
        },
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:10", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "Beh009RepeatedGitTool"), None)
    assert report is not None
    reasons = report.get("verdict_reasons") or []
    assert any("repeated git activity" in r for r in reasons)
    evidence = report.get("key_evidence") or []
    assert any("repeated git" in e for e in evidence)


def test_verdict_no_meaningful_data_yields_benign(client):
    """No meaningful risk data yields session_verdict benign and observe."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "benign-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "BenignTool", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "summary": "Tool detected"},
        "endpoint": {"id": "ep-benign", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "BenignTool"), None)
    assert report is not None
    assert report.get("session_verdict") == "benign"
    assert report.get("recommended_action") == "observe"
    reasons = report.get("verdict_reasons") or []
    assert any("low risk" in r.lower() or "no strong" in r.lower() for r in reasons)


def test_verdict_recommended_action_maps_correctly(client):
    """recommended_action maps: high_risk->contain, risky->review, interesting->review, benign->observe."""
    headers = _auth(client)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    # risk_class None => session_risk None => benign; R1 (0.25) => interesting; R3 => risky; R4 => high_risk
    tools_config = [
        ("ActionHighRisk", "R4", 0.9, "high_risk", "contain"),
        ("ActionRisky", "R3", 0.8, "risky", "review"),
        ("ActionInteresting", "R2", None, "interesting", "review"),
        ("ActionBenign", None, None, "benign", "observe"),
    ]
    for i, (tool_name, risk_class, conf, expected_verdict, expected_action) in enumerate(tools_config):
        t = (base + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        tool_payload = {"name": tool_name, "class": "B", "version": "0.1"}
        if conf is not None:
            tool_payload["attribution_confidence"] = conf
        action_payload = {"type": "exec", "summary": "Detected"}
        if risk_class is not None:
            action_payload["risk_class"] = risk_class
        body = {
            "event_id": f"action-map-{i}",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": t,
            "tool": tool_payload,
            "action": action_payload,
            "endpoint": {"id": "ep-action", "hostname": "host", "os": "Darwin"},
        }
        if expected_verdict == "interesting":
            body["session_timeline"] = [
                {"at": "13:04:02", "label": "LLM", "type": "llm"},
                {"at": "13:04:05", "label": "shell", "type": "shell_exec"},
            ]
        r = client.post(f"{API}/events", json=body, headers=headers)
        assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    for tool_name, _rc, _c, expected_verdict, expected_action in tools_config:
        report = next((s for s in items if s["tool"] == tool_name), None)
        assert report is not None, f"Missing report for {tool_name}"
        assert report.get("session_verdict") == expected_verdict, f"{tool_name} verdict"
        assert report.get("recommended_action") == expected_action, f"{tool_name} action"


def test_verdict_reasons_include_triggering_factors(client):
    """verdict_reasons list includes the factors that drove the verdict."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "reasons-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "ReasonsTool", "class": "B", "version": "0.1", "attribution_confidence": 0.85},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-reasons", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "ReasonsTool"), None)
    assert report is not None
    reasons = report.get("verdict_reasons") or []
    assert len(reasons) >= 1
    assert report.get("session_verdict") == "high_risk"


def test_verdict_low_confidence_suppresses_escalation(client):
    """Low attribution_confidence can suppress escalation from high_risk/risky."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "lowconf-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "LowConfTool", "class": "B", "version": "0.1", "attribution_confidence": 0.4},
        "action": {"type": "exec", "risk_class": "R4", "summary": "Would be high risk"},
        "endpoint": {"id": "ep-lowconf", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "LowConfTool"), None)
    assert report is not None
    assert report.get("session_risk") == 1.0
    verdict = report.get("session_verdict")
    assert verdict in ("risky", "interesting"), "high_risk should be downgraded when confidence < 0.6"
    reasons = report.get("verdict_reasons") or []
    assert any("confidence" in r.lower() for r in reasons)


def test_policy_preview_high_risk_high_confidence_contain_or_block(client):
    """High-risk, high-confidence session yields would_contain or would_block and corroborating reasons."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "pp-high-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicyPreviewHighRisk", "class": "B", "version": "0.1", "attribution_confidence": 0.85},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-pp-high", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:11", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicyPreviewHighRisk"), None)
    assert report is not None
    preview = report.get("policy_preview")
    assert preview in ("would_contain", "would_block")
    reasons = report.get("policy_preview_reasons") or []
    assert any(
        phrase in " ".join(reasons).lower()
        for phrase in ("sensitive", "confidence", "containment", "contain", "block", "corroborat")
    )


def test_policy_preview_risky_yields_would_audit(client):
    """Risky session yields would_audit and audit-threshold reasons."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "pp-risky-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicyPreviewRisky", "class": "B", "version": "0.1", "attribution_confidence": 0.75},
        "action": {"type": "exec", "risk_class": "R3", "summary": "Moderate risk"},
        "endpoint": {"id": "ep-pp-risky", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicyPreviewRisky"), None)
    assert report is not None
    assert report.get("policy_preview") == "would_audit"
    reasons = report.get("policy_preview_reasons") or []
    assert any("audit" in r.lower() or "threshold" in r.lower() for r in reasons)


def test_policy_preview_interesting_yields_would_observe(client):
    """Interesting session yields would_observe."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "pp-int-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicyPreviewInteresting", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-pp-int", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM", "type": "llm"},
            {"at": "13:04:05", "label": "shell", "type": "shell_exec"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicyPreviewInteresting"), None)
    assert report is not None
    assert report.get("policy_preview") == "would_observe"
    reasons = report.get("policy_preview_reasons") or []
    assert any("observe" in r.lower() for r in reasons)


def test_policy_preview_benign_yields_would_observe(client):
    """Benign or no meaningful data yields would_observe."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "pp-benign-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicyPreviewBenign", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "summary": "Tool detected"},
        "endpoint": {"id": "ep-pp-benign", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicyPreviewBenign"), None)
    assert report is not None
    assert report.get("policy_preview") == "would_observe"


def test_policy_preview_low_confidence_prevents_stronger_preview(client):
    """Low confidence prevents would_block; preview is would_contain or would_audit with confidence reason."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "pp-lowconf-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicyPreviewLowConf", "class": "B", "version": "0.1", "attribution_confidence": 0.4},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-pp-lowconf", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicyPreviewLowConf"), None)
    assert report is not None
    preview = report.get("policy_preview")
    assert preview != "would_block", "low confidence should prevent would_block"
    assert preview in ("would_contain", "would_audit")
    reasons = report.get("policy_preview_reasons") or []
    assert any("confidence" in r.lower() or "containment" in r.lower() or "contain" in r.lower() for r in reasons)


def test_policy_simulation_has_three_presets_and_valid_outcomes(client):
    """Session reports include policy_simulation and policy_simulation_reasons with observe, contain, block."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ps-benign-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicySimBenign", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "risk_class": "R2", "summary": "Tool detected"},
        "endpoint": {"id": "ep-ps-benign", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicySimBenign"), None)
    assert report is not None
    sim = report.get("policy_simulation")
    assert sim is not None
    assert set(sim.keys()) == {"observe", "contain", "block"}
    valid = {"would_observe", "would_audit", "would_contain", "would_block"}
    for k, v in sim.items():
        assert v in valid, f"policy_simulation[{k}] must be one of {valid}"
    reasons = report.get("policy_simulation_reasons") or {}
    assert set(reasons.keys()) == {"observe", "contain", "block"}
    assert report.get("policy_simulation")["observe"] == "would_observe"


def test_policy_simulation_contain_caps_when_block_would_block(client):
    """When block preset would_block, contain preset is would_contain with reasons mentioning the cap."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ps-block-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "PolicySimBlock", "class": "B", "version": "0.1", "attribution_confidence": 0.92},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-ps-block", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:11", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "PolicySimBlock"), None)
    assert report is not None
    sim = report.get("policy_simulation")
    assert sim is not None
    assert sim["observe"] == "would_observe"
    assert sim["block"] in ("would_contain", "would_block")
    if sim["block"] == "would_block":
        assert sim["contain"] == "would_contain"
        contain_reasons = (report.get("policy_simulation_reasons") or {}).get("contain") or []
        combined = " ".join(contain_reasons).lower()
        assert "contain" in combined and "block" in combined


def test_evidence_pack_high_risk_has_r4_threshold(client):
    """High-risk session has key_evidence containing R4 threshold; evidence_count matches len(key_evidence)."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ep-high-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackHighRisk", "class": "B", "version": "0.1", "attribution_confidence": 0.8},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-ev-high", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "EvidencePackHighRisk"), None)
    assert report is not None
    key_evidence = report.get("key_evidence") or []
    assert any("R4" in e and "threshold" in e.lower() for e in key_evidence)
    assert report.get("evidence_count") == len(key_evidence)


def test_evidence_pack_sensitive_and_outbound(client):
    """Session with sensitive + outbound signals has evidence phrase about sensitive and outbound."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ep-sensitive-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackSensitiveOutbound", "class": "B", "version": "0.1"},
        "action": {"type": "repo", "risk_class": "R3", "summary": "Repo modification"},
        "endpoint": {"id": "ep-ev-sensitive", "hostname": "host", "os": "Darwin"},
        "mitre_attack": {
            "techniques": [
                {"technique_id": "T1552", "tactic": "Credential Access"},
            ]
        },
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    # Need both credential/sensitive and network/outbound; add second event with network
    body2 = {
        "event_id": "ep-sensitive-ev-2",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackSensitiveOutbound", "class": "B", "version": "0.1"},
        "action": {"type": "network", "risk_class": "R2", "summary": "Network"},
        "endpoint": {"id": "ep-ev-sensitive", "hostname": "host", "os": "Darwin"},
    }
    client.post(f"{API}/events", json=body2, headers=headers)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "EvidencePackSensitiveOutbound"), None)
    assert report is not None
    key_evidence = report.get("key_evidence") or []
    combined = " ".join(key_evidence).lower()
    assert "sensitive" in combined and "outbound" in combined


def test_evidence_pack_llm_shell_git_chain(client):
    """Session with llm -> shell_exec -> git chain has evidence phrase about LLM-driven execution chain."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ep-chain-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackChain", "class": "B", "version": "0.1", "attribution_confidence": 0.85},
        "action": {"type": "exec", "risk_class": "R4", "summary": "Tool detected"},
        "endpoint": {"id": "ep-ev-chain", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM request", "type": "llm"},
            {"at": "13:04:05", "label": "bash", "type": "shell_exec"},
            {"at": "13:04:11", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "EvidencePackChain"), None)
    assert report is not None
    key_evidence = report.get("key_evidence") or []
    combined = " ".join(key_evidence).lower()
    assert "llm" in combined and "shell" in combined and "git" in combined


def test_evidence_pack_containment_preview_has_confidence_phrase(client):
    """Session with would_contain/would_block and high confidence has evidence about confidence and containment."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ep-contain-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackContain", "class": "B", "version": "0.1", "attribution_confidence": 0.85},
        "action": {"type": "exec", "risk_class": "R4", "summary": "High risk"},
        "endpoint": {"id": "ep-ev-contain", "hostname": "host", "os": "Darwin"},
        "session_timeline": [
            {"at": "13:04:02", "label": "LLM", "type": "llm"},
            {"at": "13:04:05", "label": "shell", "type": "shell_exec"},
            {"at": "13:04:11", "label": "git commit", "type": "git"},
        ],
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "EvidencePackContain"), None)
    assert report is not None
    assert report.get("policy_preview") in ("would_contain", "would_block")
    key_evidence = report.get("key_evidence") or []
    combined = " ".join(key_evidence).lower()
    assert "confidence" in combined and "containment" in combined


def test_evidence_pack_benign_empty_or_minimal(client):
    """Benign or no meaningful evidence yields key_evidence None or empty and evidence_count None or 0."""
    headers = _auth(client)
    base = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = {
        "event_id": "ep-benign-ev-1",
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": base,
        "tool": {"name": "EvidencePackBenign", "class": "B", "version": "0.1"},
        "action": {"type": "exec", "summary": "Tool detected"},
        "endpoint": {"id": "ep-ev-benign", "hostname": "host", "os": "Darwin"},
    }
    r = client.post(f"{API}/events", json=body, headers=headers)
    assert r.status_code in (200, 201)
    resp = client.get(f"{API}/session-reports", headers=headers)
    assert resp.status_code == 200
    report = next((s for s in resp.json()["items"] if s["tool"] == "EvidencePackBenign"), None)
    assert report is not None
    key_evidence = report.get("key_evidence")
    evidence_count = report.get("evidence_count")
    assert key_evidence is None or len(key_evidence) == 0
    assert evidence_count is None or evidence_count == 0
