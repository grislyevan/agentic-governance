"""Session aggregation and risk signal mapping for agent session reports.

Builds session reports from stored detection events: groups by endpoint + tool
within a time window, computes duration, and maps action/technique data to
human-readable risk signals. No new risk taxonomy; uses existing payload fields.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from schemas.session_report import SessionReport, SessionReportActions

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# MITRE tactic -> human-readable risk signal label (lowercase, one or two words)
_TACTIC_TO_RISK_LABEL: dict[str, str] = {
    "Credential Access": "credential access",
    "Collection": "data collection",
    "Execution": "execution",
    "Exfiltration": "exfiltration",
    "Persistence": "persistence",
    "Command and Control": "command and control",
    "Impact": "impact",
    "Defense Evasion": "defense evasion",
    "Lateral Movement": "lateral movement",
    "Privilege Escalation": "privilege escalation",
    "Reconnaissance": "reconnaissance",
    "Resource Development": "resource development",
    "Initial Access": "initial access",
}

# action.type (schema enum) -> risk signal label
_ACTION_TYPE_TO_LABEL: dict[str, str] = {
    "repo": "repo modification",
    "exec": "shell execution",
    "write": "file write",
    "read": "file read",
    "network": "network access",
    "privileged": "privileged access",
    "removal": "removal",
    "observe": "observe",
}

# Default session gap: events within this many minutes belong to same session
DEFAULT_SESSION_GAP_MINUTES = 15


def fetch_events_for_sessions(
    db: "Session",
    tenant_filter: Any,
    *,
    endpoint_id: str | None = None,
    observed_after: datetime | None = None,
    observed_before: datetime | None = None,
    limit: int = 500,
) -> list[tuple[datetime, str, str | None, dict[str, Any]]]:
    """Query detection events and return (observed_at, tool_name, endpoint_id, payload)."""
    from models.event import Event

    q = (
        db.query(Event)
        .filter(tenant_filter)
        .filter(Event.event_type == "detection.observed")
        .filter(Event.tool_name.isnot(None))
        .filter(Event.tool_name != "")
    )
    if endpoint_id:
        q = q.filter(Event.endpoint_id == endpoint_id)
    if observed_after:
        q = q.filter(Event.observed_at >= observed_after)
    if observed_before:
        q = q.filter(Event.observed_at <= observed_before)
    rows = q.order_by(Event.observed_at).limit(limit).all()

    result: list[tuple[datetime, str, str | None, dict[str, Any]]] = []
    for e in rows:
        observed = e.observed_at
        if observed and observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        result.append((observed, e.tool_name or "", e.endpoint_id, e.payload or {}))
    return result


def risk_signals_from_payload(payload: dict[str, Any]) -> list[str]:
    """Derive human-readable risk signal labels from a single event payload.

    Uses action.type, action.risk_class, and mitre_attack.techniques.
    Returns deduplicated, lowercase labels.
    """
    signals: set[str] = set()

    action = payload.get("action") or {}
    action_type = action.get("type")
    if action_type and action_type in _ACTION_TYPE_TO_LABEL:
        label = _ACTION_TYPE_TO_LABEL[action_type]
        if label != "observe":
            signals.add(label)

    mitre = payload.get("mitre_attack") or {}
    techniques = mitre.get("techniques") or []
    for t in techniques:
        if isinstance(t, dict):
            tactic = t.get("tactic")
            if tactic and tactic in _TACTIC_TO_RISK_LABEL:
                signals.add(_TACTIC_TO_RISK_LABEL[tactic])

    return sorted(signals)


def aggregate_events_into_sessions(
    events: list[tuple[datetime, str, str | None, dict[str, Any]]],
    *,
    session_gap_minutes: int = DEFAULT_SESSION_GAP_MINUTES,
    endpoint_id: str | None = None,
) -> list[SessionReport]:
    """Group (observed_at, tool_name, endpoint_id, payload) into sessions.

    Consecutive events for the same (endpoint_id, tool_name) within
    session_gap_minutes belong to one session. Returns one SessionReport per
    session with duration and aggregated risk signals. Action counts are
    left as N/A (null) when deriving from detection events only.
    """
    if not events:
        return []

    # Sort by observed_at
    sorted_events = sorted(events, key=lambda x: x[0])
    gap_delta = timedelta(minutes=session_gap_minutes)
    sessions: list[list[tuple[datetime, str, str | None, dict[str, Any]]]] = []
    current: list[tuple[datetime, str, str | None, dict[str, Any]]] = []
    current_key: tuple[str | None, str] | None = None

    for observed_at, tool_name, ep_id, payload in sorted_events:
        key = (ep_id, tool_name or "")
        if not key[1]:
            continue
        if current_key is None:
            current_key = key
            current = [(observed_at, tool_name or "", ep_id, payload)]
            continue
        if key != current_key:
            if current:
                sessions.append(current)
            current_key = key
            current = [(observed_at, tool_name or "", ep_id, payload)]
            continue
        last_observed = current[-1][0]
        if observed_at - last_observed > gap_delta:
            if current:
                sessions.append(current)
            current = [(observed_at, tool_name or "", ep_id, payload)]
        else:
            current.append((observed_at, tool_name or "", ep_id, payload))

    if current:
        sessions.append(current)

    reports: list[SessionReport] = []
    for group in sessions:
        if not group:
            continue
        times = [g[0] for g in group]
        started_at = min(times)
        ended_at = max(times)
        duration_seconds = int((ended_at - started_at).total_seconds())
        tool_name = group[0][1]
        ep_id = endpoint_id or group[0][2]

        all_signals: set[str] = set()
        for _t, _tn, _e, payload in group:
            for s in risk_signals_from_payload(payload):
                all_signals.add(s)

        reports.append(
            SessionReport(
                tool=tool_name,
                duration_seconds=duration_seconds,
                started_at=started_at,
                ended_at=ended_at,
                endpoint_id=ep_id,
                actions=SessionReportActions(),
                actions_note="N/A: aggregated from detection events only",
                risk_signals=sorted(all_signals),
            )
        )

    return reports
