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
    type: str = Field(description="Entry type: llm, shell_exec, file_write, file_delete, network, etc.")


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
    first_trigger_type: str | None = Field(default=None, description="Trigger that initiated scan when alert-triggered")
    trigger_source: str | None = Field(default=None, description="Telemetry source for trigger (polling, native, mixed)")
    alert_triggered_scans: int | None = Field(default=None, description="Number of alert-triggered scans in session")
    suppressed_triggers: int | None = Field(default=None, description="Suppressed duplicate triggers in window")
    top_behavior_chains: list[str] | None = Field(default=None, description="Derived behavior chains e.g. llm_call -> shell_exec")
    session_timeline: list[SessionTimelineEntry] | None = Field(
        default=None,
        description="Ordered timeline of actions (at, label, type) when available from collector",
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
    if report.session_timeline:
        lines.append("")
        lines.append("timeline:")
        for entry in report.session_timeline:
            lines.append(f"  {entry.at} {entry.label}")
    return "\n".join(lines)
