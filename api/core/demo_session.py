"""Canned session report for demos when real session list is empty."""

from __future__ import annotations

from datetime import datetime, timezone

from schemas.session_report import SessionReport, SessionReportActions, SessionTimelineEntry

DEMO_SESSION_ID = "demo-session-canned"
DEMO_SESSION_START = datetime(2026, 3, 15, 13, 4, 2, tzinfo=timezone.utc)
DEMO_SESSION_END = datetime(2026, 3, 15, 13, 5, 30, tzinfo=timezone.utc)


def get_canned_demo_session() -> SessionReport:
    """Return a fixed session report for demos (empty product, sales)."""
    return SessionReport(
        id=DEMO_SESSION_ID,
        session_report_id=DEMO_SESSION_ID,
        tool="Claude Code",
        duration_seconds=88,
        started_at=DEMO_SESSION_START,
        ended_at=DEMO_SESSION_END,
        endpoint_id="demo-endpoint-1",
        actions=SessionReportActions(),
        actions_note="Demo: canned session for empty product",
        risk_signals=["shell execution", "file write", "repo modification"],
        session_risk=0.75,
        session_confidence=0.88,
        top_risk_signals=["shell execution", "file write", "repo modification"],
        session_verdict="risky",
        recommended_action="review",
        verdict_reasons=["session_risk at or above R3 threshold", "agentic behavior chains present"],
        policy_preview="would_audit",
        policy_preview_reasons=["session meets audit threshold"],
        policy_simulation={
            "observe": "would_observe",
            "contain": "would_contain",
            "block": "would_block",
        },
        policy_simulation_reasons={
            "observe": ["low enforcement under observe preset"],
            "contain": ["confidence sufficient for containment preview"],
            "block": ["would block under block preset"],
        },
        key_evidence=[
            "session_risk at or above R3 threshold",
            "LLM-driven execution chain included shell and git modification",
        ],
        evidence_count=2,
        session_timeline=[
            SessionTimelineEntry(at="13:04:02", label="LLM request", type="llm"),
            SessionTimelineEntry(at="13:04:05", label="bash npm install", type="shell_exec", process_name="bash", pid=4201, parent_process_name="node"),
            SessionTimelineEntry(at="13:04:11", label="write package.json", type="file_write", process_name="node", pid=4202),
            SessionTimelineEntry(at="13:04:14", label="git commit", type="git", process_name="git", pid=4203),
        ],
        timeline_summary={"llm": 1, "shell_exec": 1, "file_write": 1, "git": 1},
        top_behavior_chains=["llm -> shell_exec", "shell_exec -> file_write", "file_write -> git"],
    )
