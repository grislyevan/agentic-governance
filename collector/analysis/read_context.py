"""Sensitive read context classification: targeted vs broad-scan vs background vs isolated.

Enriches BEH-006 evidence so analysts can distinguish targeted credential access
from IDE/indexer/background reads. Does not change scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from telemetry.event_store import FileReadEvent


class _HasPathAndTimestamp(Protocol):
    path: str
    timestamp: Any


@dataclass
class ReadContext:
    """Classification of a set of file read events."""

    read_count: int
    unique_paths: int
    burst_duration: float
    read_pattern: str


def _timestamp_seconds(e: _HasPathAndTimestamp) -> float:
    t = e.timestamp
    if hasattr(t, "timestamp"):
        return t.timestamp()
    return 0.0


def classify_read_context(events: list[_HasPathAndTimestamp]) -> ReadContext:
    """Classify read pattern from event list: targeted_read, broad_scan, background_index, isolated_read.

    Heuristics:
    - read_count, unique_paths, burst_duration (time span of reads)
    - targeted_read: few paths, short burst, moderate count
    - broad_scan: many unique paths or high path diversity
    - background_index: many reads in a sustained burst
    - isolated_read: single or very few reads
    """
    if not events:
        return ReadContext(
            read_count=0,
            unique_paths=0,
            burst_duration=0.0,
            read_pattern="isolated_read",
        )
    paths = set(e.path for e in events if getattr(e, "path", None))
    unique_paths = len(paths)
    read_count = len(events)
    times = [_timestamp_seconds(e) for e in events]
    if not times:
        burst_duration = 0.0
    else:
        burst_duration = max(times) - min(times)
    if burst_duration < 0:
        burst_duration = 0.0

    if read_count <= 2 and unique_paths <= 2:
        return ReadContext(
            read_count=read_count,
            unique_paths=unique_paths,
            burst_duration=burst_duration,
            read_pattern="isolated_read",
        )
    if read_count <= 8 and unique_paths <= 5 and burst_duration < 30.0:
        return ReadContext(
            read_count=read_count,
            unique_paths=unique_paths,
            burst_duration=burst_duration,
            read_pattern="targeted_read",
        )
    if read_count >= 20 and burst_duration > 5.0:
        return ReadContext(
            read_count=read_count,
            unique_paths=unique_paths,
            burst_duration=burst_duration,
            read_pattern="background_index",
        )
    if unique_paths >= 10 or (read_count > 0 and unique_paths / read_count > 0.85):
        return ReadContext(
            read_count=read_count,
            unique_paths=unique_paths,
            burst_duration=burst_duration,
            read_pattern="broad_scan",
        )
    return ReadContext(
        read_count=read_count,
        unique_paths=unique_paths,
        burst_duration=burst_duration,
        read_pattern="targeted_read",
    )
