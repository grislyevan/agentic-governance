"""emission_coordinator: event building, emitting, IPC broadcast, enforcement.

Extracted from _process_detection and _emit_cleared_events in orchestrator.py
to isolate all emission concerns:
  - Event building (build_event)
  - Emitter calls (emitter.emit)
  - IPC broadcast (pipe_server)
  - Enforcement dispatch (enforcer.enforce)
  - Approval hold logic (ApprovalHoldManager)
  - detection.cleared events for vanished tools
"""

from __future__ import annotations

import logging
from typing import Any, Union

from probe.models import TriggerContext

from engine.policy import PolicyDecision
from enforcement.enforcer import Enforcer, EnforcementResult
from enforcement.approval_hold import ApprovalHoldManager, HoldConfig
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from agent.state import StateDiffer
from scanner.base import ScanResult
from event_builder import build_event
from engine.session_timeline import timeline_summary_from_entries
from coordinator.scoring_coordinator import ScoringResult

logger = logging.getLogger(__name__)

AnyEmitter = Union[EventEmitter, HttpEmitter, TcpEmitter]


# ---------------------------------------------------------------------------
# emit_detection: emit the full detection → policy → (optional enforcement) chain
# ---------------------------------------------------------------------------


def emit_detection(
    scan: ScanResult,
    scoring: ScoringResult,
    *,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    sensitivity: str,
    emitter: AnyEmitter,
    enforcer: Enforcer | None,
    state_differ: StateDiffer | None,
    verbose: bool,
    scan_summary: dict[str, list[dict[str, Any]]] | None = None,
    trigger_context: TriggerContext | None = None,
    session_timeline: list[dict[str, Any]] | None = None,
    cross_tree_correlation: dict[str, Any] | None = None,
    possible_continuation: dict[str, Any] | None = None,
    agent_status: dict[str, Any] | None = None,
    config: dict | None = None,
    pipe_server: Any = None,
) -> int:
    """Emit detection / policy / enforcement events for one scored detection.

    Parameters
    ----------
    scan:       The ScanResult being processed.
    scoring:    Pre-computed ScoringResult (must not be suppressed).
    Returns the number of events successfully emitted.
    """
    if scoring.suppressed:
        # Caller should have checked; add to suppressed bucket and return early
        if scan_summary is not None:
            scan_summary.setdefault("suppressed", []).append(
                {
                    "tool": scan.tool_name,
                    "reason": scoring.suppression_reason,
                }
            )
        if verbose:
            print(
                f"  {scan.tool_name}: suppressed (credibility gate: confidence={scoring.confidence:.4f})"
            )
        return 0

    confidence = scoring.confidence
    conf_class = scoring.confidence_class
    policy_decision = scoring.decision  # guaranteed non-None when not suppressed

    # scan_summary bucket
    if scan_summary is not None:
        bucket = conf_class.lower()
        scan_summary.setdefault(bucket, []).append(
            {
                "tool": scan.tool_name,
                "tool_class": scan.tool_class or "A",
                "policy": policy_decision.decision_state,
                "reason": (scan.action_summary or "").strip()
                or policy_decision.rule_id
                or "detected",
            }
        )

    # StateDiffer gate
    if state_differ is not None:
        changed, reasons = state_differ.is_changed(
            tool_name=scan.tool_name,
            tool_class=scan.tool_class or "A",
            confidence=confidence,
            decision_state=policy_decision.decision_state,
            detected=True,
        )
        if not changed:
            if verbose:
                print(f"  {scan.tool_name}: state unchanged — skipping")
            return 0
        if verbose and reasons:
            print(f"  {scan.tool_name}: change detected — {', '.join(reasons)}")

    if verbose:
        print(f"\n  Confidence: {confidence:.4f} ({conf_class})")
        print(
            f"  Signals — P:{scan.signals.process:.2f} F:{scan.signals.file:.2f} "
            f"N:{scan.signals.network:.2f} I:{scan.signals.identity:.2f} "
            f"B:{scan.signals.behavior:.2f}"
        )
        if scan.penalties:
            print(f"  Penalties: {scan.penalties}")
        if scan.evasion_boost > 0:
            print(f"  Evasion boost: +{scan.evasion_boost:.2f}")

    events_emitted = 0

    timeline_summary = (
        timeline_summary_from_entries(session_timeline) if session_timeline else None
    )
    detection_event = build_event(
        event_type="detection.observed",
        endpoint_id=endpoint_id,
        actor_id=actor_id,
        session_id=session_id,
        trace_id=trace_id,
        scan=scan,
        confidence=confidence,
        sensitivity=sensitivity,
        correlation_context=None,  # handled by caller via scan_summary
        trigger_context=trigger_context,
        session_timeline=session_timeline,
        timeline_summary=timeline_summary,
        cross_tree_correlation=cross_tree_correlation,
        possible_continuation=possible_continuation,
        agent_status=agent_status,
    )

    if verbose:
        print(f"  Emitting detection.observed event...")
    if emitter.emit(detection_event):
        events_emitted += 1
        if state_differ is not None:
            state_differ.update(
                tool_name=scan.tool_name,
                tool_class=scan.tool_class or "A",
                confidence=confidence,
                decision_state=policy_decision.decision_state,
                detected=True,
            )

    if pipe_server and policy_decision.decision_state in (
        "detect",
        "warn",
        "block",
        "approval_required",
    ):
        from collector.ipc.protocol import EVT_DETECTION, make_event

        pipe_server.broadcast(
            make_event(
                EVT_DETECTION,
                {
                    "tool_name": scan.tool_name,
                    "decision_state": policy_decision.decision_state,
                    "confidence": confidence,
                },
            )
        )

    if verbose:
        print(
            f"  Policy: {policy_decision.decision_state} "
            f"(rule={policy_decision.rule_id})"
        )

    policy_event = build_event(
        event_type="policy.evaluated",
        endpoint_id=endpoint_id,
        actor_id=actor_id,
        session_id=session_id,
        trace_id=trace_id,
        scan=scan,
        confidence=confidence,
        sensitivity=sensitivity,
        parent_event_id=detection_event["event_id"],
        policy=policy_decision,
        correlation_context=None,
        trigger_context=trigger_context,
        session_timeline=session_timeline,
    )

    if verbose:
        print(f"  Emitting policy.evaluated event...")
    if emitter.emit(policy_event):
        events_emitted += 1

    # ------------------------------------------------------------------
    # Enforcement
    # ------------------------------------------------------------------
    should_enforce = False
    hold_result = None

    if enforcer:
        if policy_decision.decision_state == "block":
            should_enforce = True
        elif policy_decision.decision_state == "approval_required":
            hold_cfg_dict = (config or {}).get("approval_hold", {})
            hold_mgr = ApprovalHoldManager(
                api_url=(config or {}).get("api_url", ""),
                api_key=(config or {}).get("api_key", ""),
                config=HoldConfig.from_dict(hold_cfg_dict),
            )
            # Suspend target processes while waiting for a human decision when
            # the enforcer is in active posture.  This is the behaviour that
            # makes "approval_required" actually block execution: processes are
            # SIGSTOP'd until the analyst approves (SIGCONT) or denies (kill).
            # In passive/audit posture we log and wait but do not freeze.
            _active_posture = enforcer is not None and enforcer.posture == "active"
            hold_result = hold_mgr.wait_for_decision(
                event_id=detection_event["event_id"],
                tool_name=scan.tool_name or "unknown",
                tool_class=scan.tool_class or "A",
                confidence_band=conf_class.lower(),
                confidence_score=confidence,
                policy_rule_id=policy_decision.rule_id,
                endpoint_id=endpoint_id,
                pids=scoring.pids if _active_posture else None,
                suspend_on_hold=_active_posture,
                max_suspend_seconds=hold_cfg_dict.get("max_suspend_seconds", 300),
            )
            should_enforce = hold_result.decision == "denied"
            if verbose:
                hold_tag = "SUSPENDED" if hold_result.hold_effective else "WATCHED"
                outcome = (
                    "denied → enforcing" if should_enforce else "approved → allowing"
                )
                print(
                    f"  Approval hold [{hold_tag}] resolved: {outcome} "
                    f"(timed_out={hold_result.timed_out})"
                )

    if should_enforce and enforcer:
        network_elevated = "NET" in (policy_decision.rule_id or "")
        enf_result = enforcer.enforce(
            decision=policy_decision,
            tool_name=scan.tool_name or "unknown",
            tool_class=scan.tool_class or "A",
            pids=scoring.pids or None,
            network_elevated=network_elevated,
            process_patterns=scan.process_patterns,
        )
        if hold_result is not None:
            enf_result.hold_effective = hold_result.hold_effective
        if verbose:
            tag = "AUDIT" if enf_result.simulated else "LIVE"
            print(
                f"  Enforcement [{tag}]: {enf_result.tactic} "
                f"({'OK' if enf_result.success else 'FAILED'}) "
                f"- {enf_result.detail}"
            )

        if enf_result.allow_listed:
            event_type = "enforcement.allow_listed"
        elif enf_result.rate_limited:
            event_type = "enforcement.rate_limited"
        elif enf_result.simulated:
            event_type = "enforcement.simulated"
        else:
            event_type = "enforcement.applied"

        enforcement_event = build_event(
            event_type=event_type,
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            scan=scan,
            confidence=confidence,
            sensitivity=sensitivity,
            parent_event_id=policy_event["event_id"],
            policy=policy_decision,
            enforcement=enf_result,
            trigger_context=trigger_context,
            session_timeline=session_timeline,
        )
        if verbose:
            print(f"  Emitting {event_type} event...")
        if emitter.emit(enforcement_event):
            events_emitted += 1

    return events_emitted


# ---------------------------------------------------------------------------
# emit_cleared_events (was _emit_cleared_events in orchestrator.py)
# ---------------------------------------------------------------------------


def emit_cleared_events(
    state_differ: StateDiffer,
    detected_tools: set[str],
    scan_failures: set[str],
    *,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    sensitivity: str,
    emitter: AnyEmitter,
    verbose: bool,
    trigger_context: TriggerContext | None = None,
) -> int:
    """Emit detection.cleared for tools that vanished since the last cycle."""
    events_emitted = 0
    for tool_name in state_differ.cleared_tools(detected_tools, scan_failures):
        if verbose:
            print(f"\n  {tool_name}: no longer detected — emitting detection.cleared")
        cleared_scan = ScanResult(
            tool_name=tool_name,
            detected=False,
            tool_class=state_differ.get_last_class(tool_name),
            tool_version=None,
            action_type="removal",
            action_risk="R1",
            action_summary=f"{tool_name} is no longer detected on this endpoint",
        )
        cleared_event = build_event(
            event_type="detection.cleared",
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            scan=cleared_scan,
            confidence=0.0,
            sensitivity=sensitivity,
            trigger_context=trigger_context,
        )
        if emitter.emit(cleared_event):
            events_emitted += 1
        state_differ.mark_cleared(tool_name)
    return events_emitted
