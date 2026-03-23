"""Sliding-window rate limiter for enforcement actions."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

logger = logging.getLogger(__name__)


class EnforcementRateLimiter:
    """Caps enforcement actions per minute using a sliding window."""

    def __init__(self, max_per_minute: int = 5) -> None:
        self._max_per_minute = max_per_minute
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def allow(self) -> bool:
        """Return True if enforcement is allowed, False if rate-limited."""
        with self._lock:
            self._prune()
            return len(self._timestamps) < self._max_per_minute

    def record(self) -> None:
        """Record an enforcement action."""
        with self._lock:
            self._timestamps.append(time.monotonic())

    @property
    def recent_count(self) -> int:
        """Number of enforcements in the current window."""
        with self._lock:
            self._prune()
            return len(self._timestamps)

    def _prune(self) -> None:
        cutoff = time.monotonic() - 60.0
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
