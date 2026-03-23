"""Source weighting for trigger confidence and fidelity. Not used in core detection semantics."""

from __future__ import annotations

# Use only for trigger confidence, escalation urgency, and fidelity reporting.
# Core detection in engine/confidence.py does not use these weights.
SOURCE_WEIGHT: dict[str, float] = {
    "native": 1.0,
    "mixed": 0.85,
    "polling": 0.65,
}


def weight_trigger_confidence(confidence: float, source: str) -> float:
    """Scale trigger confidence by telemetry source weight."""
    w = SOURCE_WEIGHT.get(source, 0.65)
    return min(1.0, confidence * w)
