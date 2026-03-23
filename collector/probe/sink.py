"""Protocol for probe delta consumers (sink)."""

from __future__ import annotations

from typing import Protocol

from probe.models import ProbeDelta


class TelemetrySink(Protocol):
    """Sink for probe deltas. Probe-enabled providers call push_delta when they have new/changed events."""

    def push_delta(self, delta: ProbeDelta) -> None:
        """Accept a probe delta from a provider. Called from the probe loop thread."""
        ...
