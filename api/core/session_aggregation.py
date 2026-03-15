"""Session aggregation and risk signal mapping for agent session reports.

Builds session reports from stored detection events: groups by endpoint + tool
within a time window, computes duration, and maps action/technique data to
human-readable risk signals. No new risk taxonomy; uses existing payload fields.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from schemas.session_report import SessionReport, SessionReportActions, SessionTimelineEntry

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

# action.risk_class -> numeric session risk (0-1)
_RISK_CLASS_TO_SCORE: dict[str, float] = {
    "R1": 0.25,
    "R2": 0.50,
    "R3": 0.75,
    "R4": 1.0,
}

# Timeline entry type -> chain step name (skip sequence boundaries)
_TIMELINE_TYPE_TO_STEP: dict[str, str] = {
    "llm": "llm_call",
    "shell_exec": "shell_exec",
    "exec": "shell_exec",
    "file_write": "file_write",
    "file_modified": "file_write",
    "file_delete": "file_write",
    "network": "outbound_activity",
    "git": "git_modification",
}
_SKIP_TIMELINE_TYPES = frozenset({"sequence_start", "sequence_end"})


def _session_confidence_from_events(
    group: list[tuple[datetime, str, str | None, dict[str, Any]]],
) -> float | None:
    """Max tool.attribution_confidence across events in the session. None if none present."""
    values: list[float] = []
    for _t, _tn, _e, payload in group:
        if not isinstance(payload, dict):
            continue
        conf = (payload.get("tool") or {}).get("attribution_confidence")
        if conf is not None and isinstance(conf, (int, float)):
            v = float(conf)
            if 0 <= v <= 1:
                values.append(v)
    return max(values) if values else None


def _session_risk_from_events(
    group: list[tuple[datetime, str, str | None, dict[str, Any]]],
) -> float | None:
    """Max risk_class score in session (R1=0.25 .. R4=1.0). None if no risk_class present."""
    scores: list[float] = []
    for _t, _tn, _e, payload in group:
        if not isinstance(payload, dict):
            continue
        rc = (payload.get("action") or {}).get("risk_class")
        if rc and rc in _RISK_CLASS_TO_SCORE:
            scores.append(_RISK_CLASS_TO_SCORE[rc])
    return max(scores) if scores else None


def _top_risk_signals_from_events(
    group: list[tuple[datetime, str, str | None, dict[str, Any]]],
    risk_signals_fn: Any,
    top_n: int = 10,
) -> list[str]:
    """Ordered list of risk signal labels by count across events (top N)."""
    counts: dict[str, int] = {}
    for _t, _tn, _e, payload in group:
        for label in risk_signals_fn(payload):
            counts[label] = counts.get(label, 0) + 1
    sorted_labels = sorted(counts.keys(), key=lambda k: (-counts[k], k))
    return sorted_labels[:top_n] if sorted_labels else []


def _top_behavior_chains_from_timeline(
    session_timeline: list[SessionTimelineEntry],
    max_chains: int = 5,
) -> list[str]:
    """Derive behavior chain strings (from_step -> to_step) from consecutive timeline entry types."""
    if not session_timeline or len(session_timeline) < 2:
        return []
    steps: list[str] = []
    for e in session_timeline:
        t = (e.type or "").strip()
        if t in _SKIP_TIMELINE_TYPES:
            continue
        step = _TIMELINE_TYPE_TO_STEP.get(t)
        if step is None:
            step = "observe"
        steps.append(step)
    edge_counts: dict[tuple[str, str], int] = {}
    for i in range(len(steps) - 1):
        a, b = steps[i], steps[i + 1]
        if a == "observe" or b == "observe":
            continue
        key = (a, b)
        edge_counts[key] = edge_counts.get(key, 0) + 1
    chains = [f"{a} -> {b}" for (a, b), _ in sorted(edge_counts.items(), key=lambda x: (-x[1], x[0]))]
    return chains[:max_chains] if chains else []


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
        session_timeline: list[SessionTimelineEntry] | None = None
        timeline_summary: dict[str, int] | None = None
        for _t, _tn, _e, payload in group:
            for s in risk_signals_from_payload(payload):
                all_signals.add(s)
            if isinstance(payload, dict):
                raw_summary = payload.get("timeline_summary")
                if isinstance(raw_summary, dict) and all(
                    isinstance(k, str) and isinstance(v, int) for k, v in raw_summary.items()
                ):
                    timeline_summary = raw_summary
            raw_timeline = payload.get("session_timeline") if isinstance(payload, dict) else None
            if isinstance(raw_timeline, list) and raw_timeline:
                try:
                    session_timeline = [
                        SessionTimelineEntry(
                            at=e.get("at", ""),
                            label=e.get("label", ""),
                            type=e.get("type", ""),
                            process_name=e.get("process_name"),
                            pid=e.get("pid"),
                            parent_pid=e.get("parent_pid"),
                            parent_process_name=e.get("parent_process_name"),
                        )
                        for e in raw_timeline
                        if isinstance(e, dict)
                    ]
                    if not session_timeline:
                        session_timeline = None
                except Exception:
                    session_timeline = session_timeline  # keep previous if parse fails

        session_confidence = _session_confidence_from_events(group)
        session_risk = _session_risk_from_events(group)
        top_risk_signals_list = _top_risk_signals_from_events(group, risk_signals_from_payload, top_n=10)
        top_behavior_chains_list: list[str] | None = None
        if session_timeline:
            top_behavior_chains_list = _top_behavior_chains_from_timeline(session_timeline, max_chains=5)

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
                session_risk=session_risk,
                session_confidence=session_confidence,
                top_risk_signals=top_risk_signals_list if top_risk_signals_list else None,
                top_behavior_chains=top_behavior_chains_list,
                session_timeline=session_timeline,
                timeline_summary=timeline_summary,
            )
        )

    return reports
