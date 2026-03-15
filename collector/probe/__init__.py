"""Probe subsystem for adaptive sentinel mode.

Lightweight probe loop emits deltas; probe engine applies triggers,
state machine, and budget; dispatcher requests full scan when elevated.
"""

from probe.models import ProbeDelta, TriggerContext, VigilanceContext

__all__ = [
    "ProbeDelta",
    "TriggerContext",
    "VigilanceContext",
]
