"""Canonical telemetry provider interface.

Providers push normalized events into an EventStore via push_process,
push_network, push_file, and (when supported) push_file_read. Event types
are ProcessExecEvent, NetworkConnectEvent, FileChangeEvent, and optionally
FileReadEvent. The detection engine consumes only these types; providers
do not need to implement poll_events() in this push-based design.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from telemetry.capabilities import TelemetryCapabilities

if TYPE_CHECKING:
    from telemetry.event_store import EventStore


class TelemetryProviderBase(ABC):
    """Canonical interface for agent-side telemetry providers.

    Providers start with a store and push normalized events (ProcessExecEvent,
    NetworkConnectEvent, FileChangeEvent, FileReadEvent) into it. When sentinel
    mode is enabled, probe-enabled providers may accept optional sink and
    probe_interval_ms via start() keyword arguments.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'esf', 'etw', 'ebpf', 'polling')."""
        ...

    @abstractmethod
    def available(self) -> bool:
        """Return True if this provider can run on the current platform."""
        ...

    @abstractmethod
    def start(self, store: EventStore) -> None:
        """Begin streaming events into the store."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider and release resources."""
        ...

    def capabilities(self) -> TelemetryCapabilities:
        """Return this provider's telemetry capabilities.

        Override in subclasses to report actual support. Default is a
        conservative set (e.g. no file_change/file_read) so that
        store-derived or merged capabilities can fill in.
        """
        return TelemetryCapabilities(
            has_process_exec=True,
            has_file_change=False,
            has_file_read=False,
            has_network_events=True,
            has_process_parent=True,
        )
