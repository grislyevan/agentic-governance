"""Abstract interface for telemetry providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telemetry.event_store import EventStore


class TelemetryProvider(ABC):
    """Interface for agent-side telemetry providers.

    When sentinel mode is enabled, probe-enabled providers (e.g. PollingProvider)
    may accept an optional sink and probe_interval_ms via start() keyword arguments
    to run a lightweight background probe loop that emits only deltas to the sink.
    The store is still used for full-scan cycles via poll().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g., 'esf', 'etw', 'ebpf', 'polling')."""
        ...

    @abstractmethod
    def available(self) -> bool:
        """Check whether this provider can run on the current platform."""
        ...

    @abstractmethod
    def start(self, store: EventStore) -> None:
        """Begin streaming events into the store."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the provider and release resources."""
        ...
