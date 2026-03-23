"""Glue between probe engine, ScanDispatcher, and optional vigilance state/buffer."""

from __future__ import annotations

from probe.engine import ProbeEngine
from probe.models import TriggerContext
from probe.scan_dispatcher import ScanDispatcher
from probe.state_machine import create_idle


class ProbeOrchestrator:
    """Holds probe engine, optional vigilance state, and buffer; wires engine to dispatcher."""

    def __init__(
        self,
        endpoint_id: str,
        dispatcher: ScanDispatcher,
        probe_window_seconds: int = 120,
        cooldown_seconds: int = 10,
        max_alert_scans_per_minute: int = 4,
        max_elevations_per_5_minutes: int = 10,
    ) -> None:
        self._endpoint_id = endpoint_id
        self._dispatcher = dispatcher
        self._vigilance = create_idle(endpoint_id)
        self._engine = ProbeEngine(
            endpoint_id=endpoint_id,
            probe_window_seconds=probe_window_seconds,
            cooldown_seconds=cooldown_seconds,
            max_alert_scans_per_minute=max_alert_scans_per_minute,
            max_elevations_per_5_minutes=max_elevations_per_5_minutes,
            on_request_scan=self._on_request_scan,
        )

    def _on_request_scan(self, ctx: TriggerContext) -> None:
        self._dispatcher.request_scan(
            self._endpoint_id,
            ctx,
            urgency="immediate",
        )

    @property
    def engine(self) -> ProbeEngine:
        """Probe engine (TelemetrySink). Use for provider.start(store, sink=orchestrator.engine)."""
        return self._engine

    @property
    def vigilance(self):
        """Current vigilance context (for future state-driven escalation)."""
        return self._vigilance
