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
    return "\n".join(lines)
