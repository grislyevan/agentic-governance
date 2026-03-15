"""In-memory rolling buffer of recent probe/canonical events for observation windows."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any

# CanonicalEvent: dict or a small typed wrapper; we use dict for flexibility with event_store events.
CanonicalEvent = dict[str, Any]


class EventBuffer:
    """Per-endpoint rolling buffer of recent events. Thread-safe."""

    def __init__(self, max_events: int = 5000, retention_seconds: float = 300.0) -> None:
        self._max_events = max_events
        self._retention_seconds = retention_seconds
        self._events: deque[tuple[datetime, CanonicalEvent]] = deque(maxlen=max_events)
        self._lock = Lock()

    def append(self, event: CanonicalEvent, ts: datetime | None = None) -> None:
        """Append an event with optional timestamp. Uses event observed_at if ts not given."""
        from datetime import timezone
        if ts is None:
            obs = event.get("observed_at") or event.get("timestamp")
            if isinstance(obs, str):
                try:
                    ts = datetime.fromisoformat(obs.replace("Z", "+00:00"))
                except ValueError:
                    ts = datetime.now(timezone.utc)
            elif hasattr(event, "timestamp"):
                ts = getattr(event, "timestamp")
            else:
                ts = datetime.now(timezone.utc)
        with self._lock:
            self._events.append((ts, event))

    def recent(self, since: datetime) -> list[CanonicalEvent]:
        """Return events with timestamp >= since, in order."""
        with self._lock:
            return [ev for t, ev in self._events if t >= since]

    def clear(self) -> None:
        """Clear the buffer."""
        with self._lock:
            self._events.clear()
