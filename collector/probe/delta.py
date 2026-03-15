"""Helpers to build ProbeDelta from provider snapshot diffs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

from probe.models import ProbeDelta


def _process_key(e: ProcessExecEvent) -> tuple[int, str, str]:
    """Stable key for process event deduplication."""
    return (e.pid, e.name or "", (e.cmdline or "")[:200])


def _network_key(e: NetworkConnectEvent) -> tuple[int, str, int]:
    """Stable key for network event deduplication."""
    return (e.pid, e.remote_addr or "", e.remote_port or 0)


def _file_key(e: FileChangeEvent) -> tuple[str, str]:
    """Stable key for file event deduplication."""
    return (e.path or "", e.action or "")


def process_delta(
    current: list[ProcessExecEvent],
    previous: list[ProcessExecEvent],
) -> list[ProcessExecEvent]:
    """Return process events in current that are new or changed vs previous."""
    prev_keys = {_process_key(e) for e in previous}
    return [e for e in current if _process_key(e) not in prev_keys]


def network_delta(
    current: list[NetworkConnectEvent],
    previous: list[NetworkConnectEvent],
) -> list[NetworkConnectEvent]:
    """Return network events in current that are new vs previous."""
    prev_keys = {_network_key(e) for e in previous}
    return [e for e in current if _network_key(e) not in prev_keys]


def file_delta(
    current: list[FileChangeEvent],
    previous: list[FileChangeEvent],
) -> list[FileChangeEvent]:
    """Return file events in current that are new vs previous."""
    prev_keys = {_file_key(e) for e in previous}
    return [e for e in current if _file_key(e) not in prev_keys]


def build_probe_delta(
    ts: datetime,
    source: Literal["polling", "native"],
    current_process: list[ProcessExecEvent],
    current_network: list[NetworkConnectEvent],
    current_file: list[FileChangeEvent],
    previous_process: list[ProcessExecEvent],
    previous_network: list[NetworkConnectEvent],
    previous_file: list[FileChangeEvent],
) -> ProbeDelta:
    """Build a ProbeDelta containing only new/changed events since previous snapshot."""
    return ProbeDelta(
        ts=ts,
        source=source,
        process_events=process_delta(current_process, previous_process),
        file_events=file_delta(current_file, previous_file),
        network_events=network_delta(current_network, previous_network),
    )
