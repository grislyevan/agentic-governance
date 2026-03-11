"""Shared event types for EDR telemetry and enrichment."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProcessExecEvent:
    timestamp: datetime
    pid: int
    ppid: int
    name: str
    cmdline: str
    username: str | None = None
    binary_path: str | None = None
    binary_hash: str | None = None


@dataclass
class NetworkConnectEvent:
    timestamp: datetime
    pid: int
    process_name: str
    remote_addr: str
    remote_port: int
    local_port: int
    protocol: str = "tcp"
    sni: str | None = None


@dataclass
class FileChangeEvent:
    timestamp: datetime
    pid: int | None
    path: str
    action: str  # created, modified, deleted, renamed
    process_name: str | None = None


@dataclass
class EnrichmentResult:
    provider: str
    query_window_start: datetime
    query_window_end: datetime
    process_events_matched: int
    network_events_matched: int
    file_events_matched: int
    original_confidence: float
    enriched_confidence: float
    band_changed: bool
    penalties_removed: list[str] = field(default_factory=list)
