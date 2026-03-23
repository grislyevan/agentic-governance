"""Agent-side telemetry: event store, capabilities, and typed events."""

from __future__ import annotations

from .capabilities import (
    TelemetryCapabilities,
    get_capabilities_from_store,
    merge_capabilities,
)
from .event_store import (
    EventStore,
    FileChangeEvent,
    FileReadEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

__all__ = [
    "EventStore",
    "FileChangeEvent",
    "FileReadEvent",
    "NetworkConnectEvent",
    "ProcessExecEvent",
    "TelemetryCapabilities",
    "get_capabilities_from_store",
    "merge_capabilities",
]
