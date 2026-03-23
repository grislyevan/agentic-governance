"""Probe engine: consumes deltas, applies triggers, enforces budget, requests scan when elevated."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Callable

from probe.budget import TriggerBudget
from probe.models import ProbeDelta, TriggerContext
from probe.source_weighting import weight_trigger_confidence
from probe.triggers import TriggerMatch, evaluate_triggers

logger = logging.getLogger(__name__)


class ProbeEngine:
    """Consumes ProbeDeltas, evaluates triggers, applies cooldown/budget, and requests full scan when allowed."""

    def __init__(
        self,
        endpoint_id: str,
        probe_window_seconds: int = 120,
        cooldown_seconds: int = 10,
        max_alert_scans_per_minute: int = 4,
        max_elevations_per_5_minutes: int = 10,
        on_request_scan: Callable[[TriggerContext], None] | None = None,
    ) -> None:
        self._endpoint_id = endpoint_id
        self._probe_window_seconds = probe_window_seconds
        self._budget = TriggerBudget(
            cooldown_seconds=cooldown_seconds,
            max_alert_scans_per_minute=max_alert_scans_per_minute,
            max_elevations_per_5_minutes=max_elevations_per_5_minutes,
            on_suppressed=self._on_suppressed,
        )
        self._on_request_scan = on_request_scan

    def _on_suppressed(self, trigger_type: str, reason: str, count: int) -> None:
        logger.debug(
            "probe.trigger_suppressed endpoint_id=%s trigger_type=%s reason=%s count=%s",
            self._endpoint_id,
            trigger_type,
            reason,
            count,
        )

    def push_delta(self, delta: ProbeDelta) -> None:
        """Accept a probe delta; evaluate triggers and possibly request a scan."""
        matches = evaluate_triggers(delta)
        if not matches:
            return
        now = delta.ts
        all_signals: list[str] = []
        best: TriggerMatch | None = None
        best_conf = 0.0
        for m in matches:
            all_signals.extend(m.signals)
            if m.confidence > best_conf:
                best_conf = m.confidence
                best = m
        if best is None:
            return
        trigger_type = best.trigger_type
        weighted_conf = weight_trigger_confidence(best_conf, delta.source)
        allowed, suppressed = self._budget.allow_trigger(trigger_type, now)
        if not allowed:
            return
        if not self._budget.allow_scan(now):
            self._on_suppressed(trigger_type, "budget", 1)
            return
        if self._on_request_scan is None:
            return
        ctx = TriggerContext(
            scan_reason="alert",
            trigger_type=trigger_type,
            trigger_source=delta.source,
            trigger_confidence=weighted_conf,
            trigger_signals=list(dict.fromkeys(all_signals)),
            trigger_time=now,
            probe_window_seconds=self._probe_window_seconds,
            cooldown_applied=False,
            suppressed_duplicates=suppressed,
        )
        try:
            self._on_request_scan(ctx)
            self._budget.record_scan(now)
        except Exception:
            logger.debug("on_request_scan failed", exc_info=True)
