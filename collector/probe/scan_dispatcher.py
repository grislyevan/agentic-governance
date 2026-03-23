"""Single entry point for requesting a full scan (scheduled, alert-triggered, or manual)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from probe.models import TriggerContext


@dataclass
class ScanRequestResult:
    """Result of a scan request (queued or rejected)."""

    accepted: bool
    reason: str = ""


class ScanDispatcher:
    """Dispatches full-scan requests. Used by daemon scheduled path, probe engine, and manual triggers."""

    def __init__(
        self,
        endpoint_id: str,
        set_pending_trigger: Callable[[TriggerContext | None], None] | None = None,
        wake_scan_loop: Callable[[], None] | None = None,
    ) -> None:
        self._endpoint_id = endpoint_id
        self._set_pending_trigger = set_pending_trigger
        self._wake_scan_loop = wake_scan_loop

    def request_scan(
        self,
        endpoint_id: str,
        trigger_context: TriggerContext | None,
        urgency: Literal["background", "immediate"],
    ) -> ScanRequestResult:
        """Request a full scan. If trigger_context is None, treated as scheduled."""
        if self._set_pending_trigger is not None:
            self._set_pending_trigger(trigger_context)
        if self._wake_scan_loop is not None:
            self._wake_scan_loop()
        return ScanRequestResult(accepted=True, reason="queued")
