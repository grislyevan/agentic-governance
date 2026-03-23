"""Agent telemetry diagnostics: uptime, scan duration, trees, patterns.

Exposed in event payload as agent_status for future diagnostics/status UI.
Does not persist on server in this sprint; payload-only.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScanDiagnostics:
    """One scan cycle's diagnostics."""
    trees_count: int = 0
    duration_ms: float = 0.0
    patterns_triggered: list[str] = field(default_factory=list)


class DiagnosticsAccumulator:
    """Accumulates agent diagnostics across scan cycles."""

    def __init__(
        self,
        rolling_scans: int = 30,
    ) -> None:
        self._start_time: float | None = None
        self._rolling_scans: int = rolling_scans
        self._scan_times: deque[float] = deque(maxlen=rolling_scans)
        self._scan_durations_ms: deque[float] = deque(maxlen=rolling_scans)
        self._trees_per_scan: deque[int] = deque(maxlen=rolling_scans)
        self._last_patterns: list[str] = []
        self._event_count: int = 0
        self._last_event_count_reset: float = 0.0

    def start_scan(self) -> None:
        """Call at start of each scan cycle."""
        if self._start_time is None:
            self._start_time = time.time()
        self._scan_times.append(time.time())

    def end_scan(
        self,
        trees_count: int = 0,
        patterns_triggered: list[str] | None = None,
    ) -> None:
        """Call at end of each scan cycle."""
        if self._scan_times:
            elapsed_ms = (time.time() - self._scan_times[-1]) * 1000.0
            self._scan_durations_ms.append(elapsed_ms)
            self._trees_per_scan.append(trees_count)
        self._last_patterns = list(patterns_triggered or [])

    def record_events_delta(self, delta: int) -> None:
        """Optional: record events pushed this cycle (if instrumentation added)."""
        self._event_count += delta

    def get_status(
        self,
        provider_name: str = "unknown",
        event_counts: dict[str, int] | None = None,
        capability_drift: list[str] | None = None,
        tamper_vectors: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build agent_status dict for event payload.

        tamper_vectors: evasion/tamper detector vector IDs (e.g. E1-global-hook, E6-agent-kill-loop)
        and optionally \"capability_drift\" when telemetry capability loss is present (E3 contract).
        """
        now = time.time()
        uptime_s = (now - self._start_time) if self._start_time is not None else 0
        scans = len(self._scan_durations_ms)
        avg_ms = sum(self._scan_durations_ms) / scans if scans else 0.0
        scans_per_min = (scans / (uptime_s / 60.0)) if uptime_s > 0 else 0.0
        trees_last = self._trees_per_scan[-1] if self._trees_per_scan else 0
        events_per_sec = 0.0
        if self._event_count > 0 and self._last_event_count_reset > 0 and uptime_s > 0:
            events_per_sec = self._event_count / uptime_s
        out: dict[str, Any] = {
            "uptime_seconds": round(uptime_s, 1),
            "scans_per_minute": round(scans_per_min, 1),
            "avg_scan_ms": round(avg_ms, 1),
            "trees_per_scan": trees_last,
            "patterns_triggered": self._last_patterns[:20],
            "provider": provider_name,
        }
        if event_counts is not None:
            out["events_in_store"] = dict(event_counts)
        if capability_drift is not None:
            out["capability_drift"] = capability_drift
        if tamper_vectors is not None and len(tamper_vectors) > 0:
            out["tamper_vectors"] = tamper_vectors
        return out
