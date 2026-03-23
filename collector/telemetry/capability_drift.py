"""Capability drift detection: report when telemetry capabilities disappear.

Compares current (merged) capabilities to the previous scan. If a capability
that was True becomes False (e.g. file_read or network_events), it is reported
so the server or dashboard can alert. Does not change detection outcome.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .capabilities import TelemetryCapabilities

_CAPABILITY_NAMES = (
    "has_process_exec",
    "has_file_change",
    "has_file_read",
    "has_network_events",
    "has_process_parent",
)

_last: "TelemetryCapabilities | None" = None
_consecutive_missing: dict[str, int] = {}  # capability name -> scans missing (for debounce)


def check_drift(
    current: "TelemetryCapabilities",
    debounce_scans: int = 2,
) -> list[str]:
    """Compare current capabilities to last known; return list of drifted capability names.

    On first call, no drift. When a capability that was True becomes False, it is
    included in the result after debounce_scans consecutive scans (default 2) to
    avoid false positives after provider switch or restart.
    """
    global _last, _consecutive_missing
    drifted: list[str] = []
    if _last is None:
        _last = current
        return drifted

    for name in _CAPABILITY_NAMES:
        was = getattr(_last, name, False)
        now = getattr(current, name, False)
        if not now:
            if was:
                _consecutive_missing[name] = _consecutive_missing.get(name, 0) + 1
            elif name in _consecutive_missing:
                _consecutive_missing[name] += 1
            if _consecutive_missing.get(name, 0) >= debounce_scans:
                drifted.append(name)
        else:
            _consecutive_missing.pop(name, None)

    _last = current
    # Expose short names for agent_status (e.g. file_read not has_file_read)
    return [n.replace("has_", "", 1) if n.startswith("has_") else n for n in drifted]


def _reset_for_test() -> None:
    """Reset module state for tests. Do not use in production."""
    global _last, _consecutive_missing
    _last = None
    _consecutive_missing = {}
