"""Dataclasses for probe deltas, trigger context, and vigilance state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)


@dataclass
class ProbeDelta:
    """Lightweight delta from a probe cycle: new or changed events only."""

    ts: datetime
    source: Literal["polling", "native"]
    process_events: list[ProcessExecEvent]
    file_events: list[FileChangeEvent]
    network_events: list[NetworkConnectEvent]
    # identity_events omitted until a concrete identity event source exists


@dataclass
class TriggerContext:
    """Canonical context for why a scan was requested. Attach to scan invocations and emitted events."""

    scan_reason: Literal["scheduled", "alert", "manual"]
    trigger_type: str
    trigger_source: Literal["polling", "native", "mixed"]
    trigger_confidence: float
    trigger_signals: list[str]
    trigger_time: datetime
    probe_window_seconds: int
    cooldown_applied: bool
    suppressed_duplicates: int = 0


VigilanceState = Literal["IDLE", "OBSERVING", "ELEVATED", "COOLDOWN"]


@dataclass
class VigilanceContext:
    """Per-endpoint (or per-tool) vigilance state for the sentinel state machine."""

    endpoint_id: str
    tool: str | None
    state: VigilanceState
    state_since: datetime
    observation_expires_at: datetime | None
    cooldown_expires_at: datetime | None
    trigger_budget_window_start: datetime
    alert_triggered_scans_in_window: int
