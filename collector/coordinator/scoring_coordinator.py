"""scoring_coordinator: confidence scoring, policy evaluation, suppression.

Extracted from _process_detection in orchestrator.py to isolate all scoring
concerns:
  - Confidence scoring (compute_confidence, classify_confidence)
  - Suppression / credibility gating (_should_suppress_emission)
  - Network context building
  - Policy evaluation (evaluate_policy)
  - Tamper floor application (apply_tamper_floor)
  - Session violation tracking (record_violation, get_violation_count)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from engine.confidence import classify_confidence, compute_confidence
from engine.network import DEFAULT_ALLOWLIST_PATH, _matches_allowlist
from engine.policy import (
    NetworkContext,
    PolicyDecision,
    apply_tamper_floor,
    evaluate_policy,
)
from engine.container import is_containerized as check_containerized
from decision_engine import (
    _maybe_prune_violation_counts,
    _should_suppress_emission,
    _suppressed_reason,
    get_violation_count,
    record_violation,
)
from scanner.base import ScanResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ScoringResult:
    """All outputs from scoring one detection."""

    confidence: float = 0.0
    confidence_class: str = "Low"
    decision: PolicyDecision | None = None
    suppressed: bool = False
    suppression_reason: str = ""
    network_context: NetworkContext | None = None
    pids: set[int] = field(default_factory=set)
    containerized: bool | None = None


# ---------------------------------------------------------------------------
# score_detection: main entry point
# ---------------------------------------------------------------------------


def score_detection(
    scan: ScanResult,
    *,
    sensitivity: str,
    endpoint_id: str,
    network_allowlist: set[str] | None = None,
    agent_status: dict[str, Any] | None = None,
) -> ScoringResult:
    """Compute confidence, evaluate policy, and return a ScoringResult.

    Returns a ScoringResult with suppressed=True when the credibility gate
    fires; in that case no policy evaluation or enforcement should occur.
    """
    from coordinator.scan_coordinator import _extract_pids  # avoid circular

    confidence = compute_confidence(scan)
    conf_class = classify_confidence(confidence)

    if _should_suppress_emission(scan, confidence):
        return ScoringResult(
            confidence=confidence,
            confidence_class=conf_class,
            suppressed=True,
            suppression_reason=_suppressed_reason(scan, confidence),
        )

    pids = _extract_pids(scan)
    containerized = check_containerized(next(iter(pids))) if pids else None
    net_ctx = _build_network_context(scan, network_allowlist)

    _maybe_prune_violation_counts()
    session_key = (endpoint_id, scan.tool_name or "unknown")
    prior_violations = get_violation_count(session_key)

    actor_trust_tier = (
        "T0" if (scan.tool_class or "A") in ("C", "D") or not scan.tool_name else "T1"
    )

    policy_decision = evaluate_policy(
        confidence=confidence,
        confidence_class=conf_class,
        tool_class=scan.tool_class or "A",
        sensitivity=sensitivity,
        action_risk=scan.action_risk,
        is_containerized=containerized,
        net_ctx=net_ctx,
        prior_violations=prior_violations,
        actor_trust_tier=actor_trust_tier,
    )

    if agent_status and agent_status.get("tamper_vectors"):
        policy_decision = apply_tamper_floor(
            policy_decision, agent_status["tamper_vectors"]
        )

    # Accumulate session violations for warn-or-higher decisions
    _VIOLATION_STATES = frozenset({"warn", "approval_required", "block"})
    if policy_decision.decision_state in _VIOLATION_STATES:
        record_violation(session_key)

    return ScoringResult(
        confidence=confidence,
        confidence_class=conf_class,
        decision=policy_decision,
        suppressed=False,
        suppression_reason="",
        network_context=net_ctx,
        pids=pids,
        containerized=containerized,
    )


# ---------------------------------------------------------------------------
# Network context helper (was _build_network_context in orchestrator.py)
# ---------------------------------------------------------------------------


def _build_network_context(
    scan: ScanResult,
    allowlist: set[str] | None,
) -> NetworkContext | None:
    """Build a NetworkContext from scan evidence and the allowlist."""
    if allowlist is None:
        return None

    connections = scan.evidence_details.get("connections", [])
    if not connections:
        return None

    total = len(connections)
    unknown_dests: list[str] = []
    for conn in connections:
        dest = conn.get("remote_address") or conn.get("dest") or ""
        if isinstance(dest, str) and dest:
            host = dest.split(":")[0].lower()
            if host and not _matches_allowlist(
                addr=host, hostname=None, allowlist=allowlist
            ):
                unknown_dests.append(dest)

    if not unknown_dests:
        return NetworkContext(
            unknown_connections=0,
            unknown_destinations=[],
            total_connections=total,
        )

    return NetworkContext(
        unknown_connections=len(unknown_dests),
        unknown_destinations=unknown_dests[:10],
        total_connections=total,
    )
