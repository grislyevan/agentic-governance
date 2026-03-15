"""Build agent session reports from event store and scan results.

Produces the human-readable "Agent Session Detected" summary: tool, duration,
action counts (file reads/writes, shell commands, model calls), and risk signals.
Uses existing telemetry and scan result fields; no new risk taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from telemetry.event_store import EventStore
    from scanner.base import ScanResult

_SHELL_NAMES: frozenset[str] = frozenset({
    "bash", "sh", "zsh", "fish", "csh", "tcsh", "dash",
    "cmd", "powershell", "pwsh",
})

# Host/substring patterns that indicate LLM API (model) calls
_LLM_HOST_PATTERNS: tuple[str, ...] = (
    "anthropic", "openai", "api.anthropic", "api.openai",
    "ollama", "localhost",  # local inference
)


def _risk_signals_from_scan(scan: "ScanResult") -> list[str]:
    """Derive human-readable risk labels from a ScanResult (action_risk, action_type, evidence)."""
    signals: set[str] = set()

    action_type = (scan.action_type or "").strip().lower()
    if action_type == "repo":
        signals.add("repo modification")
    elif action_type == "exec":
        signals.add("shell execution")
    elif action_type == "write":
        signals.add("file write")
    elif action_type in ("network", "privileged", "removal") and action_type:
        signals.add(action_type.replace("_", " "))

    risk = scan.action_risk or "R1"
    if risk in ("R3", "R4"):
        if "repo" in (scan.action_summary or "").lower() or action_type == "repo":
            signals.add("repo modification")
        if "credential" in (scan.action_summary or "").lower():
            signals.add("credential access")

    evidence = scan.evidence_details or {}
    patterns = evidence.get("behavioral_patterns") or []
    for p in patterns:
        if isinstance(p, dict) and p.get("pattern_id") == "BEH-006":
            signals.add("credential access")
        elif isinstance(p, dict) and p.get("pattern_id") == "BEH-007":
            signals.add("repo modification")

    return sorted(signals)


@dataclass
class SessionReportData:
    """One session report: tool, duration, action counts, risk signals."""

    tool: str
    duration_seconds: int
    started_at: datetime
    ended_at: datetime
    file_reads: int | None
    file_writes: int | None
    shell_commands: int | None
    model_calls: int | None
    actions_note: str | None
    risk_signals: list[str]


def build_session_reports(
    event_store: "EventStore",
    detected_scans: list["ScanResult"],
) -> list[SessionReportData]:
    """Build one session report per detected tool from event store and scan results.

    Duration and action counts come from telemetry in the store when available;
    otherwise uses scan window or N/A. Risk signals come from scan result fields.
    """
    reports: list[SessionReportData] = []

    process_events = event_store.get_process_events()
    network_events = event_store.get_network_events()
    file_events = event_store.get_file_events()

    if process_events:
        start_ts = min(e.timestamp for e in process_events)
        end_ts = max(e.timestamp for e in process_events)
    elif file_events:
        start_ts = min(e.timestamp for e in file_events)
        end_ts = max(e.timestamp for e in file_events)
    elif network_events:
        start_ts = min(e.timestamp for e in network_events)
        end_ts = max(e.timestamp for e in network_events)
    else:
        start_ts = end_ts = datetime.now(timezone.utc)

    if start_ts.tzinfo is None:
        start_ts = start_ts.replace(tzinfo=timezone.utc)
    if end_ts.tzinfo is None:
        end_ts = end_ts.replace(tzinfo=timezone.utc)
    duration_seconds = int((end_ts - start_ts).total_seconds())

    file_writes = sum(
        1 for e in file_events
        if e.action in ("created", "modified")
    )
    shell_commands = sum(
        1 for e in process_events
        if e.name.lower().split("/")[-1].split("\\")[-1] in _SHELL_NAMES
    )
    model_calls = sum(
        1 for e in network_events
        if any(pat in (e.remote_addr or "").lower() or pat in (e.sni or "").lower()
               for pat in _LLM_HOST_PATTERNS)
    )
    file_reads: int | None = None  # Telemetry schema has no read events yet

    has_telemetry = bool(process_events or file_events or network_events)
    actions_note = None if has_telemetry else "N/A: no telemetry in window"

    for scan in detected_scans:
        tool_name = scan.tool_name or "Unknown Agent"
        risk_signals = _risk_signals_from_scan(scan)
        reports.append(
            SessionReportData(
                tool=tool_name,
                duration_seconds=duration_seconds,
                started_at=start_ts,
                ended_at=end_ts,
                file_reads=file_reads,
                file_writes=file_writes if has_telemetry else None,
                shell_commands=shell_commands if has_telemetry else None,
                model_calls=model_calls if has_telemetry else None,
                actions_note=actions_note,
                risk_signals=risk_signals,
            )
        )

    if not detected_scans and (process_events or file_events or network_events):
        reports.append(
            SessionReportData(
                tool="Unknown Agent",
                duration_seconds=duration_seconds,
                started_at=start_ts,
                ended_at=end_ts,
                file_reads=file_reads,
                file_writes=file_writes if has_telemetry else None,
                shell_commands=shell_commands if has_telemetry else None,
                model_calls=model_calls if has_telemetry else None,
                actions_note=actions_note,
                risk_signals=[],
            )
        )

    return reports


def format_session_report_for_cli(report: SessionReportData) -> str:
    """Format a single session report as the example CLI output."""
    duration_m = report.duration_seconds // 60
    duration_s = report.duration_seconds % 60
    duration_str = f"{duration_m}m{duration_s}s"

    def _n(x: int | None) -> str:
        return str(x) if x is not None else "N/A"

    lines = [
        "Agent Session Detected",
        "",
        f"tool: {report.tool}",
        f"duration: {duration_str}",
        "",
        "actions:",
        f"- {_n(report.file_reads)} file reads",
        f"- {_n(report.file_writes)} file writes",
        f"- {_n(report.shell_commands)} shell commands",
        f"- {_n(report.model_calls)} model calls",
    ]
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
