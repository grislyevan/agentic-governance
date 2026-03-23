"""Policy ladder presets for sentinel mode. Map to existing posture and rule semantics."""

from __future__ import annotations

# Alert-triggered scans may run faster; enforcement still requires stricter policy thresholds.
# These presets map to existing posture (passive, audit, active) and optional auto_enforce_threshold.
POLICY_LADDER_PRESETS: dict[str, tuple[str, float | None]] = {
    "observe": ("passive", None),   # Emit detections only
    "contain": ("audit", None),     # Flag and optionally suspend risky tool context
    "block": ("active", 0.75),      # Enforce immediately for very high-confidence, high-risk chains
}
