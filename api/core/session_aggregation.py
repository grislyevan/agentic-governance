"""Session aggregation and risk signal mapping for agent session reports.

Builds session reports from stored detection events: groups by endpoint + tool
within a time window, computes duration, and maps action/technique data to
human-readable risk signals. No new risk taxonomy; uses existing payload fields.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from core.config import settings
from core.subchain_extractor import extract_strongest_subchain
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


def default_session_lookback_window() -> tuple[datetime, datetime]:
    """Return (observed_after, observed_before) for the default session list/by-id window.
    Aligns list and get-by-id so any session in the list can be fetched by id.
    Window length is configurable via settings.session_lookback_days (env: SESSION_LOOKBACK_DAYS).
    """
    now = datetime.now(timezone.utc)
    observed_after = now - timedelta(days=settings.session_lookback_days)
    return observed_after, now


def _session_id(endpoint_id: str | None, tool_name: str, started_at: datetime) -> str:
    """Stable synthetic id for a session (endpoint + tool + started_at)."""
    key = f"{endpoint_id or ''}|{tool_name}|{started_at.isoformat()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

# action.risk_class -> numeric session risk (0-1)
_RISK_CLASS_TO_SCORE: dict[str, float] = {
    "R1": 0.25,
    "R2": 0.50,
    "R3": 0.75,
    "R4": 1.0,
}

# Verdict thresholds and min confidence for escalation
_VERDICT_HIGH_RISK_THRESHOLD = 1.0
_VERDICT_RISKY_THRESHOLD = 0.75
_VERDICT_INTERESTING_RISK = 0.25
_MIN_CONFIDENCE_TO_ESCALATE = 0.6

# Policy preview: block vs contain thresholds (strict policy hypothetical)
_POLICY_PREVIEW_BLOCK_CONFIDENCE = 0.9
_POLICY_PREVIEW_CONTAIN_MIN_CONFIDENCE = 0.8

# Timeline entry type -> canonical chain step (same vocabulary as timeline; see docs/session-report-vocabulary.md)
_TIMELINE_TYPE_TO_STEP: dict[str, str] = {
    "llm": "llm",
    "shell_exec": "shell_exec",
    "exec": "shell_exec",
    "file_write": "file_write",
    "file_modified": "file_write",
    "file_delete": "file_write",
    "network": "network",
    "git": "git",
}
_SKIP_TIMELINE_TYPES = frozenset({"sequence_start", "sequence_end"})


def _detection_codes_from_payload(payload: dict[str, Any]) -> set[str]:
    """Extract detection_codes from event payload (evidence_details or evidence)."""
    if not isinstance(payload, dict):
        return set()
    evidence = payload.get("evidence_details") or payload.get("evidence") or {}
    codes = evidence.get("detection_codes") if isinstance(evidence, dict) else []
    if not isinstance(codes, list):
        return set()
    return {str(c) for c in codes if c}


def _beh009_broader_impact_from_group(
    group: list[tuple[datetime, str, str | None, dict[str, Any]]],
) -> dict[str, bool]:
    """Extract BEH-009 broader-impact flags from session event payloads.

    Returns dict with multi_file and repeated_git True if any event has
    BEH-009 pattern evidence with those flags set.
    """
    multi_file = False
    repeated_git = False
    for _t, _tn, _e, payload in group:
        if not isinstance(payload, dict):
            continue
        evidence = payload.get("evidence_details") or payload.get("evidence") or {}
        patterns = evidence.get("behavioral_patterns") if isinstance(evidence, dict) else []
        if not isinstance(patterns, list):
            continue
        for p in patterns:
            if not isinstance(p, dict) or p.get("pattern_id") != "BEH-009":
                continue
            ev = p.get("evidence") if isinstance(p.get("evidence"), dict) else {}
            flags = ev.get("flags") if isinstance(ev.get("flags"), dict) else {}
            multi_file_val = flags.get("multi_file_change") if flags else ev.get("multi_file_change")
            repeated_git_val = flags.get("repeated_git_activity") if flags else ev.get("repeated_git_activity")
            if multi_file_val is True:
                multi_file = True
            if repeated_git_val is True:
                repeated_git = True
            if multi_file and repeated_git:
                return {"multi_file": True, "repeated_git": True}
    return {"multi_file": multi_file, "repeated_git": repeated_git}


def _has_file_write_or_git(
    top_behavior_chains: list[str] | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
) -> bool:
    """True if session has file write or git activity (from chains or risk signals)."""
    signals = set((risk_signals or []) + (top_risk_signals or []))
    if "file write" in signals or "repo modification" in signals:
        return True
    chains = top_behavior_chains or []
    for chain in chains:
        if " -> " not in chain:
            continue
        a, b = chain.split(" -> ", 1)
        a, b = a.strip(), b.strip()
        if a == "file_write" or b == "file_write" or a == "git" or b == "git":
            return True
    return False


# Top-k mean for session confidence: reduces impact of a single high outlier.
_SESSION_CONFIDENCE_TOP_K = 3


def _session_confidence_from_events(
    group: list[tuple[datetime, str, str | None, dict[str, Any]]],
) -> float | None:
    """Robust aggregate of tool.attribution_confidence: mean of top-k (default 3) per session.

    If fewer than k values, uses mean of all. Reduces spike inflation from one noisy event.
    """
    values: list[float] = []
    for _t, _tn, _e, payload in group:
        if not isinstance(payload, dict):
            continue
        conf = (payload.get("tool") or {}).get("attribution_confidence")
        if conf is not None and isinstance(conf, (int, float)):
            v = float(conf)
            if 0 <= v <= 1:
                values.append(v)
    if not values:
        return None
    k = min(_SESSION_CONFIDENCE_TOP_K, len(values))
    top = sorted(values, reverse=True)[:k]
    return sum(top) / len(top)


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


def _compute_verdict_and_reasons(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> tuple[str | None, list[str]]:
    """Compute session verdict and explicit reasons (rule-based). Returns (verdict, reasons)."""
    reasons: list[str] = []
    signals = set((risk_signals or []) + (top_risk_signals or []))
    chains = top_behavior_chains or []
    risk = session_risk if session_risk is not None else 0.0
    conf = session_confidence if session_confidence is not None else 0.0

    # Base ladder
    if risk >= _VERDICT_HIGH_RISK_THRESHOLD:
        verdict = "high_risk"
        reasons.append("session_risk reached R4 threshold")
    elif risk >= _VERDICT_RISKY_THRESHOLD:
        verdict = "risky"
        reasons.append("session_risk at or above R3 threshold")
    elif risk >= _VERDICT_INTERESTING_RISK or chains:
        verdict = "interesting"
        if chains:
            reasons.append("agentic behavior chains present")
        if risk >= _VERDICT_INTERESTING_RISK:
            reasons.append("moderate session risk")
    else:
        verdict = "benign"
        reasons.append("low risk, no strong signals")

    # Elevate: credential/secret access + outbound/LLM
    sensitive_labels = {"credential access", "data collection", "repo modification"}
    outbound_labels = {"network access", "execution", "exfiltration", "shell execution"}
    has_sensitive = bool(signals & sensitive_labels)
    has_outbound = bool(signals & outbound_labels)
    if has_sensitive and has_outbound and verdict != "high_risk":
        verdict = "high_risk"
        reasons.append("sensitive access followed by outbound activity")

    # Elevate: llm -> shell_exec -> git chain with high risk (canonical chain tokens)
    llm_shell = "llm -> shell_exec" in chains
    shell_git = "shell_exec -> git" in chains
    if llm_shell and shell_git and risk >= _VERDICT_RISKY_THRESHOLD and verdict != "high_risk":
        verdict = "high_risk"
        reasons.append("behavior chain included llm -> shell_exec -> git")

    # Elevate: BEH-001 (shell fan-out) + file write or git: interesting -> risky
    codes = detection_codes or set()
    if "DETEC-BEH-CORE-01" in codes and _has_file_write_or_git(
        top_behavior_chains, risk_signals, top_risk_signals
    ):
        if verdict == "interesting":
            verdict = "risky"
            reasons.append("autonomous shell burst followed by repository modification")

    # BEH-009 broader impact: plain-language reasons when agent chain touched multiple files or repeated git
    impact = beh009_broader_impact or {}
    if "DETEC-BEH-CORE-04" in codes:
        if impact.get("multi_file"):
            reasons.append("agent execution chain touched multiple files")
        if impact.get("repeated_git"):
            reasons.append("repeated git activity in agent execution chain")

    # Suppress escalation if confidence too low
    if verdict in ("high_risk", "risky") and conf < _MIN_CONFIDENCE_TO_ESCALATE and conf > 0:
        if verdict == "high_risk":
            verdict = "risky"
            reasons.append("confidence too low to escalate to high_risk")
        else:
            verdict = "interesting"
            reasons.append("confidence too low to escalate to risky")

    return (verdict, reasons)


def _session_verdict_from_report_inputs(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> str | None:
    """Compute session verdict from aggregated report inputs."""
    verdict, _ = _compute_verdict_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    return verdict


def _recommended_action_from_verdict(verdict: str | None) -> str | None:
    """Map verdict to recommended action."""
    if verdict is None:
        return None
    if verdict == "high_risk":
        return "contain"
    if verdict == "risky":
        return "review"
    if verdict == "interesting":
        return "review"
    if verdict == "benign":
        return "observe"
    return None


def _verdict_reasons_from_report_inputs(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> list[str]:
    """Compute explicit verdict reasons from report inputs."""
    _, reasons = _compute_verdict_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    return reasons


def _compute_policy_preview_and_reasons(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> tuple[str | None, list[str]]:
    """Compute policy preview outcome and reasons (strict policy hypothetical). Returns (preview, reasons)."""
    verdict, _ = _compute_verdict_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    reasons: list[str] = []
    signals = set((risk_signals or []) + (top_risk_signals or []))
    chains = top_behavior_chains or []
    conf = session_confidence if session_confidence is not None else 0.0

    sensitive_labels = {"credential access", "data collection", "repo modification"}
    outbound_labels = {"network access", "execution", "exfiltration", "shell execution"}
    has_sensitive = bool(signals & sensitive_labels)
    has_outbound = bool(signals & outbound_labels)
    llm_shell = "llm -> shell_exec" in chains
    shell_git = "shell_exec -> git" in chains
    strong_corroboration = (has_sensitive and has_outbound) or (llm_shell and shell_git)

    if verdict == "high_risk":
        if conf >= _POLICY_PREVIEW_BLOCK_CONFIDENCE and strong_corroboration:
            return (
                "would_block",
                [
                    "high-risk session with corroborated agentic execution chain",
                    "confidence sufficient for block",
                ],
            )
        if conf >= _POLICY_PREVIEW_CONTAIN_MIN_CONFIDENCE:
            reasons.append("session meets containment threshold")
            if has_sensitive and has_outbound:
                reasons.append("sensitive access followed by outbound activity")
            return ("would_contain", reasons)
        reasons.append("confidence below blocking threshold; containment preferred")
        if has_sensitive and has_outbound:
            reasons.append("sensitive access followed by outbound activity")
        return ("would_contain", reasons)
    if verdict == "risky":
        reasons_audit = ["session meets audit threshold"]
        risk = session_risk if session_risk is not None else 0.0
        if risk >= _VERDICT_HIGH_RISK_THRESHOLD and conf < _POLICY_PREVIEW_CONTAIN_MIN_CONFIDENCE and conf > 0:
            reasons_audit.append("low confidence prevents stronger action")
        return ("would_audit", reasons_audit)
    return ("would_observe", ["observe-only under strict policy"])


def _policy_preview_from_session(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> str | None:
    """Compute policy preview outcome from session report inputs."""
    preview, _ = _compute_policy_preview_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    return preview


def _policy_preview_reasons_from_session(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> list[str]:
    """Compute policy preview reasons from session report inputs."""
    _, reasons = _compute_policy_preview_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    return reasons


def _compute_policy_simulation(
    strict_preview: str | None,
    strict_reasons: list[str],
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Derive policy_simulation and policy_simulation_reasons from strict policy preview.

    observe: always would_observe. contain: cap at would_contain if strict is would_block.
    block: use strict outcome and reasons as-is.
    """
    sim: dict[str, str] = {}
    reasons: dict[str, list[str]] = {}
    outcome = strict_preview if strict_preview else "would_observe"
    sim["observe"] = "would_observe"
    reasons["observe"] = ["observe-only under observe policy"]
    if outcome == "would_block":
        sim["contain"] = "would_contain"
        reasons["contain"] = [
            "would block under block policy; under contain policy outcome is contain",
            *[r for r in strict_reasons if r],
        ]
    else:
        sim["contain"] = outcome
        reasons["contain"] = list(strict_reasons) if strict_reasons else ["observe-only under contain policy"]
    sim["block"] = outcome
    reasons["block"] = list(strict_reasons) if strict_reasons else []
    return (sim, reasons)


_MAX_KEY_EVIDENCE_ITEMS = 8


def _build_evidence_pack(
    session_risk: float | None,
    session_confidence: float | None,
    risk_signals: list[str],
    top_risk_signals: list[str] | None,
    top_behavior_chains: list[str] | None,
    detection_codes: set[str] | None = None,
    beh009_broader_impact: dict[str, bool] | None = None,
) -> tuple[list[str], int]:
    """Build curated key evidence list (executive summary). Returns (key_evidence, evidence_count).

    Prefer fact-like statements; reserve attribution phrasing (e.g. LLM-driven) for high-confidence
    cases (see docs/session-report-vocabulary.md).
    """
    verdict, _ = _compute_verdict_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    preview, _ = _compute_policy_preview_and_reasons(
        session_risk,
        session_confidence,
        risk_signals,
        top_risk_signals,
        top_behavior_chains,
        detection_codes,
        beh009_broader_impact,
    )
    evidence: list[str] = []
    signals = set((risk_signals or []) + (top_risk_signals or []))
    chains = top_behavior_chains or []
    risk = session_risk if session_risk is not None else 0.0
    conf = session_confidence if session_confidence is not None else 0.0
    codes = detection_codes or set()
    impact = beh009_broader_impact or {}

    sensitive_labels = {"credential access", "data collection", "repo modification"}
    outbound_labels = {"network access", "execution", "exfiltration", "shell execution"}
    has_sensitive = bool(signals & sensitive_labels)
    has_outbound = bool(signals & outbound_labels)
    llm_shell = "llm -> shell_exec" in chains
    shell_git = "shell_exec -> git" in chains

    if risk >= _VERDICT_HIGH_RISK_THRESHOLD:
        evidence.append("session reached R4 risk threshold")
    if has_sensitive and has_outbound:
        evidence.append("sensitive file access observed before outbound activity")
    if llm_shell and shell_git:
        evidence.append("LLM-driven execution chain included shell and git modification")
    if "DETEC-BEH-CORE-04" in codes and (impact.get("multi_file") or impact.get("repeated_git")):
        parts = []
        if impact.get("multi_file"):
            parts.append("multiple files")
        if impact.get("repeated_git"):
            parts.append("repeated git actions")
        evidence.append(
            "Agent execution chain touched " + " and ".join(parts) + " in the same session"
        )
    if preview in ("would_contain", "would_block") and conf >= _POLICY_PREVIEW_CONTAIN_MIN_CONFIDENCE:
        evidence.append("confidence sufficient for containment preview")
    if preview == "would_audit":
        evidence.append("session meets audit threshold")
    if verdict == "interesting" and chains:
        evidence.append("agentic behavior chains present")
    if risk >= _VERDICT_HIGH_RISK_THRESHOLD and 0 < conf < _MIN_CONFIDENCE_TO_ESCALATE:
        evidence.append("low confidence limited escalation")

    evidence = evidence[:_MAX_KEY_EVIDENCE_ITEMS]
    return (evidence, len(evidence))


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
        raw = e.payload
        if isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, str):
            try:
                payload = json.loads(raw)
                if not isinstance(payload, dict):
                    payload = {}
            except Exception:
                payload = {}
        else:
            payload = {}
        result.append((observed, e.tool_name or "", e.endpoint_id, payload))
    return result


def session_exists_by_session_id(
    db: "Session",
    tenant_filter: Any,
    session_id: str,
) -> bool:
    """Return True if any event with the given session_id exists for this tenant.

    Used as a cheap existence check when session reconstruction returns None due to
    the event window limit.
    """
    from models.event import Event

    return (
        db.query(Event.id)
        .filter(tenant_filter)
        .filter(Event.session_id == session_id)
        .limit(1)
        .first()
    ) is not None


def get_session_report_by_id(
    db: "Session",
    tenant_filter: Any,
    session_id: str,
) -> SessionReport | None:
    """Fetch events for a lookback window, aggregate into sessions, return report with given id or None.

    Lookback is the last N days (configurable via SESSION_LOOKBACK_DAYS; default 7). At most
    session_report_by_id_event_limit events (configurable via SESSION_REPORT_BY_ID_EVENT_LIMIT;
    default 500) are loaded. If the tenant has more detection events in that window, the
    target session may not be in the set and this returns None (API returns 404).
    """
    observed_after, observed_before = default_session_lookback_window()
    limit = settings.session_report_by_id_event_limit
    events = fetch_events_for_sessions(
        db,
        tenant_filter,
        observed_after=observed_after,
        observed_before=observed_before,
        limit=limit,
    )
    reports = aggregate_events_into_sessions(events, session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES)
    for report in reports:
        if report.id == session_id:
            return report
    return None


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
        detection_codes: set[str] = set()
        evasion_vectors_set: set[str] = set()
        session_timeline: list[SessionTimelineEntry] | None = None
        timeline_summary: dict[str, int] | None = None
        for _t, _tn, _e, payload in group:
            for s in risk_signals_from_payload(payload):
                all_signals.add(s)
            detection_codes |= _detection_codes_from_payload(payload)
            if isinstance(payload, dict):
                agent_status = payload.get("agent_status") or {}
                for v in agent_status.get("tamper_vectors") or []:
                    if isinstance(v, str):
                        evasion_vectors_set.add(v)
                evidence = payload.get("evidence_details") or {}
                for f in evidence.get("evasion_findings") or []:
                    if isinstance(f, dict) and f.get("vector"):
                        evasion_vectors_set.add(f["vector"])
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
        strongest_subchain_list: list[str] | None = None
        if session_timeline:
            top_behavior_chains_list = _top_behavior_chains_from_timeline(session_timeline, max_chains=5)
            strongest_subchain_list = extract_strongest_subchain(session_timeline) or None

        beh009_broader_impact = _beh009_broader_impact_from_group(group)

        risk_signals_sorted = sorted(all_signals)
        session_verdict, verdict_reasons = _compute_verdict_and_reasons(
            session_risk,
            session_confidence,
            risk_signals_sorted,
            top_risk_signals_list,
            top_behavior_chains_list,
            detection_codes,
            beh009_broader_impact,
        )
        recommended_action = _recommended_action_from_verdict(session_verdict)
        policy_preview, policy_preview_reasons = _compute_policy_preview_and_reasons(
            session_risk,
            session_confidence,
            risk_signals_sorted,
            top_risk_signals_list,
            top_behavior_chains_list,
            detection_codes,
            beh009_broader_impact,
        )
        policy_simulation, policy_simulation_reasons = _compute_policy_simulation(
            policy_preview,
            policy_preview_reasons or [],
        )
        key_evidence_list, evidence_count_val = _build_evidence_pack(
            session_risk,
            session_confidence,
            risk_signals_sorted,
            top_risk_signals_list,
            top_behavior_chains_list,
            detection_codes,
            beh009_broader_impact,
        )

        session_id = _session_id(ep_id, tool_name, started_at)
        reports.append(
            SessionReport(
                id=session_id,
                session_report_id=session_id,
                tool=tool_name,
                duration_seconds=duration_seconds,
                started_at=started_at,
                ended_at=ended_at,
                endpoint_id=ep_id,
                actions=SessionReportActions(),
                actions_note="N/A: aggregated from detection events only",
                risk_signals=risk_signals_sorted,
                session_risk=session_risk,
                session_confidence=session_confidence,
                top_risk_signals=top_risk_signals_list if top_risk_signals_list else None,
                top_behavior_chains=top_behavior_chains_list,
                strongest_subchain=strongest_subchain_list,
                session_verdict=session_verdict,
                recommended_action=recommended_action,
                verdict_reasons=verdict_reasons if verdict_reasons else None,
                policy_preview=policy_preview,
                policy_preview_reasons=policy_preview_reasons if policy_preview_reasons else None,
                policy_simulation=policy_simulation,
                policy_simulation_reasons=policy_simulation_reasons,
                key_evidence=key_evidence_list if key_evidence_list else None,
                evidence_count=evidence_count_val if key_evidence_list else None,
                session_timeline=session_timeline,
                timeline_summary=timeline_summary,
                evasion_vectors=sorted(evasion_vectors_set) if evasion_vectors_set else None,
            )
        )

    return reports
