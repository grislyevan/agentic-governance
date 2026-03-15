"""Session report schema for agent session summaries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionReportActions(BaseModel):
    """Action counts for a session (null when not available)."""

    file_reads: int | None = None
    file_writes: int | None = None
    shell_commands: int | None = None
    model_calls: int | None = None


class SessionTimelineEntry(BaseModel):
    """One entry in a session timeline narrative."""

    at: str = Field(description="Time (e.g. HH:MM:SS)")
    label: str = Field(description="Short human-readable action label")
    type: str = Field(
        description="Entry type: llm, shell_exec, file_write, file_delete, network, git, sequence_start, sequence_end, etc."
    )
    process_name: str | None = Field(default=None, description="Process name (basename) when available")
    pid: int | None = Field(default=None, description="Process ID when available")
    parent_pid: int | None = Field(default=None, description="Parent process ID when available")
    parent_process_name: str | None = Field(default=None, description="Parent process name for display")


class SessionReport(BaseModel):
    """Canonical agent session report: tool, duration, action counts, risk signals."""

    tool: str = Field(description="Tool name, e.g. Claude Cowork")
    duration_seconds: int = Field(description="Session length in seconds")
    started_at: datetime = Field(description="First event in session")
    ended_at: datetime = Field(description="Last event in session")
    endpoint_id: str | None = Field(default=None, description="Endpoint ID when scoped")
    actions: SessionReportActions = Field(default_factory=SessionReportActions)
    actions_note: str | None = Field(
        default=None,
        description="e.g. 'N/A: aggregated from detection events only'",
    )
    risk_signals: list[str] = Field(default_factory=list, description="Human-readable risk labels")
    session_risk: float | None = Field(
        default=None,
        description="Session risk 0-1 from max action.risk_class in session (R1=0.25, R2=0.5, R3=0.75, R4=1.0)",
    )
    session_confidence: float | None = Field(
        default=None,
        description="Max tool.attribution_confidence across events in the session (0-1)",
    )
    top_risk_signals: list[str] | None = Field(
        default=None,
        description="Risk signal labels ordered by frequency in session (top N)",
    )
    first_trigger_type: str | None = Field(default=None, description="Trigger that initiated scan when alert-triggered")
    trigger_source: str | None = Field(default=None, description="Telemetry source for trigger (polling, native, mixed)")
    alert_triggered_scans: int | None = Field(default=None, description="Number of alert-triggered scans in session")
    suppressed_triggers: int | None = Field(default=None, description="Suppressed duplicate triggers in window")
    top_behavior_chains: list[str] | None = Field(default=None, description="Derived behavior chains e.g. llm_call -> shell_exec")
    session_timeline: list[SessionTimelineEntry] | None = Field(
        default=None,
        description="Ordered timeline of actions (at, label, type) when available from collector",
    )
    timeline_summary: dict[str, int] | None = Field(
        default=None,
        description="Counts by entry type (e.g. llm, shell_exec, file_write, git) when available",
    )


class SessionReportListResponse(BaseModel):
    """Response for session report list endpoints."""

    items: list[SessionReport] = Field(default_factory=list)


def session_report_to_display(report: SessionReport) -> str:
    """Format a session report as the example CLI/dashboard display."""
    duration_m = report.duration_seconds // 60
    duration_s = report.duration_seconds % 60
    duration_str = f"{duration_m}m{duration_s}s"

    lines = [
        "Agent Session Detected",
        "",
        f"tool: {report.tool}",
        f"duration: {duration_str}",
        "",
        "actions:",
    ]
    actions = report.actions
    lines.append(f"- {actions.file_reads if actions.file_reads is not None else 'N/A'} file reads")
    lines.append(f"- {actions.file_writes if actions.file_writes is not None else 'N/A'} file writes")
    lines.append(f"- {actions.shell_commands if actions.shell_commands is not None else 'N/A'} shell commands")
    lines.append(f"- {actions.model_calls if actions.model_calls is not None else 'N/A'} model calls")
    if report.actions_note:
        lines.append(f"  ({report.actions_note})")
    lines.append("")
    lines.append("risk signals:")
    if report.risk_signals:
        for sig in report.risk_signals:
            lines.append(f"- {sig}")
    else:
        lines.append("- (none)")
    if report.session_risk is not None or report.session_confidence is not None:
        lines.append("")
        lines.append("session scoring:")
        if report.session_risk is not None:
            lines.append(f"- session_risk: {report.session_risk:.2f}")
        if report.session_confidence is not None:
            lines.append(f"- session_confidence: {report.session_confidence:.2f}")
    if report.top_risk_signals:
        lines.append("")
        lines.append("top risk signals:")
        for sig in report.top_risk_signals:
            lines.append(f"- {sig}")
    if report.first_trigger_type or report.trigger_source:
        lines.append("")
        lines.append("trigger:")
        if report.first_trigger_type:
            lines.append(f"- type: {report.first_trigger_type}")
        if report.trigger_source:
            lines.append(f"- source: {report.trigger_source}")
        if report.suppressed_triggers is not None:
            lines.append(f"- suppressed: {report.suppressed_triggers}")
    if report.top_behavior_chains:
        lines.append("")
        lines.append("top behavior chains:")
        for chain in report.top_behavior_chains:
            lines.append(f"- {chain}")
    if report.timeline_summary:
        lines.append("")
        lines.append("summary:")
        parts = [f"{k}: {v}" for k, v in sorted(report.timeline_summary.items())]
        lines.append("  " + ", ".join(parts))
    if report.session_timeline:
        lines.append("")
        lines.append("timeline:")
        for entry in report.session_timeline:
            lines.append(f"  {entry.at} {entry.label}")
            if entry.pid is not None or entry.parent_process_name is not None or entry.process_name is not None:
                parts = []
                if entry.pid is not None:
                    parts.append(f"pid={entry.pid}")
                if entry.parent_process_name is not None:
                    parts.append(f"parent={entry.parent_process_name}")
                if entry.process_name is not None:
                    parts.append(f"process={entry.process_name}")
                if parts:
                    lines.append("           " + " ".join(parts))
    return "\n".join(lines)
