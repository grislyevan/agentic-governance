"""Telemetry capability flags for detection resilience.

Allows detectors to adapt when a provider does not supply certain event types
(e.g. file read, process ancestry). Inferred from the event store or set
explicitly for testing and future native providers (ESF, eBPF, ETW).
"""

from __future__ import annotations

from dataclasses import dataclass

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .event_store import EventStore


@dataclass(frozen=True)
class TelemetryCapabilities:
    """Flags indicating which telemetry types are available for detection."""

    has_process_exec: bool = True
    has_file_change: bool = False
    has_file_read: bool = False
    has_network_events: bool = True
    has_process_parent: bool = True

    def gaps_affecting_detection(self) -> list[str]:
        """Return list of capability gaps that may affect behavioral detection."""
        gaps: list[str] = []
        if not self.has_process_exec:
            gaps.append("process_exec")
        if not self.has_file_change:
            gaps.append("file_change")
        if not self.has_network_events:
            gaps.append("network_events")
        if not self.has_process_parent:
            gaps.append("process_parent")
        return gaps


def get_capabilities_from_store(store: EventStore) -> TelemetryCapabilities:
    """Infer telemetry capabilities from the current event store contents.

    Conservative: assumes capabilities based on presence of events and
    provider behavior. Polling provider has process and network; file_change
    only if file events exist (e.g. from a native provider). file_read
    remains False until a read-capable provider is available.
    """
    process_events = store.get_process_events()
    file_events = store.get_file_events()
    file_read_events = store.get_file_read_events()
    network_events = store.get_network_events()

    has_process = len(process_events) > 0
    has_ppid = any(e.ppid is not None and e.ppid != 0 for e in process_events)

    return TelemetryCapabilities(
        has_process_exec=has_process,
        has_file_change=len(file_events) > 0,
        has_file_read=len(file_read_events) > 0,
        has_network_events=len(network_events) > 0,
        has_process_parent=has_ppid if has_process else True,
    )


def merge_capabilities(
    provider_cap: TelemetryCapabilities,
    store_cap: TelemetryCapabilities,
) -> TelemetryCapabilities:
    """Merge provider-reported and store-derived capabilities (OR per flag).

    Use when the active provider exposes capabilities(); merged result reflects
    both what the provider can supply and what has been observed in the store.
    """
    return TelemetryCapabilities(
        has_process_exec=provider_cap.has_process_exec or store_cap.has_process_exec,
        has_file_change=provider_cap.has_file_change or store_cap.has_file_change,
        has_file_read=provider_cap.has_file_read or store_cap.has_file_read,
        has_network_events=provider_cap.has_network_events or store_cap.has_network_events,
        has_process_parent=provider_cap.has_process_parent or store_cap.has_process_parent,
    )
