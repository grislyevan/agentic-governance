"""Policy decision helpers: credibility gating and session violation tracking.

Split from orchestrator.py to isolate policy decision support logic from
the scan orchestration loop. These functions are called by _process_detection
in orchestrator.py.
"""

from __future__ import annotations

import time

from scanner.base import ScanResult

# ---------------------------------------------------------------------------
# Session violation tracking (Section 6.4)
# ---------------------------------------------------------------------------
# Maps (endpoint_id, tool_name) -> (violation_count, last_updated_epoch)
# for the current session window.
SESSION_VIOLATION_TTL_SECONDS = 86400  # 24 hours
_session_violation_counts: dict[tuple[str, str], tuple[int, float]] = {}


def _maybe_prune_violation_counts() -> None:
    """Remove session violation entries older than SESSION_VIOLATION_TTL_SECONDS."""
    cutoff = time.monotonic() - SESSION_VIOLATION_TTL_SECONDS
    expired = [k for k, (_, ts) in _session_violation_counts.items() if ts < cutoff]
    for k in expired:
        del _session_violation_counts[k]


def get_violation_count(key: tuple[str, str]) -> int:
    """Return the current violation count for (endpoint_id, tool_name)."""
    return _session_violation_counts.get(key, (0, 0.0))[0]


def record_violation(key: tuple[str, str]) -> None:
    """Increment the violation counter for (endpoint_id, tool_name)."""
    prev_count = _session_violation_counts.get(key, (0, 0.0))[0]
    _session_violation_counts[key] = (prev_count + 1, time.monotonic())


# ---------------------------------------------------------------------------
# Credibility gating (signal credibility)
# ---------------------------------------------------------------------------
# Minimum confidence below which we suppress emission.
# Rationale: extremely low confidence is typically identity-only or artifact-only;
# emitting full detection/policy events for these reduces trust. See
# project-docs/detec-signal-credibility-architecture.md.
EMISSION_MIN_CONFIDENCE = 0.20

# Maximum confidence at which we still suppress when summary says "no signals."
# Avoids emitting the confusing case: "No X signals detected" with medium confidence.
EMISSION_NO_SIGNALS_MAX_CONFIDENCE = 0.45


def _no_signals_summary(scan: ScanResult) -> bool:
    """True when action_summary indicates no real signals (e.g. 'No X signals detected')."""
    summary = (scan.action_summary or "").strip().lower()
    return "no " in summary and " signals detected" in summary


def _should_suppress_emission(scan: ScanResult, confidence: float) -> bool:
    """True when this scan should not emit detection/policy events (credibility gating)."""
    if confidence < EMISSION_MIN_CONFIDENCE:
        return True
    if _no_signals_summary(scan) and confidence < EMISSION_NO_SIGNALS_MAX_CONFIDENCE:
        return True
    return False


def _suppressed_reason(scan: ScanResult, confidence: float) -> str:
    """Return a short reason for suppression for the analyst summary."""
    if _no_signals_summary(scan):
        return "no runtime evidence"
    if confidence < EMISSION_MIN_CONFIDENCE:
        return "artifact evidence only"
    return "credibility gate"
