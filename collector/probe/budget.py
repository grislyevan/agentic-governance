"""Cooldown and scan budget to prevent probe-triggered scan storms."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

logger = logging.getLogger(__name__)


class TriggerBudget:
    """Enforces cooldown (per-trigger-type) and alert-triggered scan budget per window."""

    def __init__(
        self,
        cooldown_seconds: int = 10,
        max_alert_scans_per_minute: int = 4,
        max_elevations_per_5_minutes: int = 10,
        on_suppressed: Callable[[str, str, int], None] | None = None,
    ) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._max_per_minute = max_alert_scans_per_minute
        self._max_per_5min = max_elevations_per_5_minutes
        self._on_suppressed = on_suppressed
        self._last_trigger_by_type: dict[str, datetime] = {}
        self._scans_in_minute: list[datetime] = []
        self._elevations_in_5min: list[datetime] = []

    def allow_trigger(
        self,
        trigger_type: str,
        now: datetime | None = None,
    ) -> tuple[bool, int]:
        """Return (allowed, suppressed_count). suppressed_count is how many of this type were suppressed recently."""
        now = now or datetime.now(timezone.utc)
        last = self._last_trigger_by_type.get(trigger_type)
        suppressed = 0
        if last is not None:
            if (now - last).total_seconds() < self._cooldown_seconds:
                suppressed = 1
                self._last_trigger_by_type[trigger_type] = now
                if self._on_suppressed:
                    try:
                        self._on_suppressed(trigger_type, "cooldown", 1)
                    except Exception:
                        logger.debug("on_suppressed callback failed", exc_info=True)
                return False, suppressed
        self._last_trigger_by_type[trigger_type] = now
        return True, 0

    def allow_scan(self, now: datetime | None = None) -> bool:
        """Return True if an alert-triggered scan is allowed under the per-minute and per-5min budget."""
        now = now or datetime.now(timezone.utc)
        cutoff_1 = now - timedelta(minutes=1)
        cutoff_5 = now - timedelta(minutes=5)
        self._scans_in_minute = [t for t in self._scans_in_minute if t > cutoff_1]
        self._elevations_in_5min = [t for t in self._elevations_in_5min if t > cutoff_5]
        if len(self._scans_in_minute) >= self._max_per_minute:
            return False
        if len(self._elevations_in_5min) >= self._max_per_5min:
            return False
        return True

    def record_scan(self, now: datetime | None = None) -> None:
        """Record that an alert-triggered scan was run."""
        now = now or datetime.now(timezone.utc)
        self._scans_in_minute.append(now)
        self._elevations_in_5min.append(now)
