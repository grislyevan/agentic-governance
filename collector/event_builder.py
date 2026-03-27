"""Event construction: canonical event dict assembly and severity computation.

Split from orchestrator.py to isolate event schema concerns from scan
orchestration and policy decision logic.
"""

from __future__ import annotations

import platform
import uuid
from datetime import datetime, timezone
from typing import Any

from probe.models import TriggerContext

from engine.attack_mapping import map_scan_result
from engine.policy import PolicyDecision
from enforcement.enforcer import EnforcementResult
from scanner.base import ScanResult

# Version map: Playbook 0.4 -> EVENT_VERSION 0.4.0
EVENT_VERSION = "0.4.0"


def _trigger_context_to_dict(ctx: TriggerContext) -> dict[str, Any]:
    """Serialize TriggerContext for event payload."""
    return {
        "scan_reason": ctx.scan_reason,
        "trigger_type": ctx.trigger_type,
        "trigger_source": ctx.trigger_source,
        "trigger_confidence": ctx.trigger_confidence,
        "trigger_signals": list(ctx.trigger_signals),
        "trigger_time": ctx.trigger_time.isoformat(),
        "probe_window_seconds": ctx.probe_window_seconds,
        "cooldown_applied": ctx.cooldown_applied,
        "suppressed_duplicates": ctx.suppressed_duplicates,
    }


def _compute_severity(
    confidence: float,
    action_risk: str,
    sensitivity: str,
    policy: PolicyDecision | None,
) -> str:
    """Map detection to severity level per Playbook Section 8."""
    risk_num = {"R1": 1, "R2": 2, "R3": 3, "R4": 4}.get(action_risk, 1)
    tier_num = {"Tier0": 0, "Tier1": 1, "Tier2": 2, "Tier3": 3}.get(sensitivity, 0)

    if policy and policy.decision_state == "block":
        if tier_num >= 3 or risk_num >= 4:
            return "S4"
        return "S3"

    if policy and policy.decision_state == "approval_required":
        if tier_num >= 2 and risk_num >= 3:
            return "S3"
        return "S2"

    if confidence >= 0.75 and risk_num >= 3:
        return "S2"

    if confidence >= 0.45:
        return "S1"

    return "S0"


def build_event(
    event_type: str,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    scan: ScanResult,
    confidence: float,
    sensitivity: str,
    parent_event_id: str | None = None,
    policy: PolicyDecision | None = None,
    enforcement: EnforcementResult | None = None,
    correlation_context: list[str] | None = None,
    trigger_context: TriggerContext | None = None,
    session_timeline: list[dict[str, Any]] | None = None,
    timeline_summary: dict[str, int] | None = None,
    cross_tree_correlation: dict[str, Any] | None = None,
    possible_continuation: dict[str, Any] | None = None,
    agent_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a canonical event dict conforming to the JSON Schema."""
    now = datetime.now(timezone.utc).isoformat()

    event_evidence: dict[str, Any] = dict(scan.evidence_details) if scan.evidence_details else {}
    event: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "observed_at": now,
        "ingested_at": now,
        "session_id": session_id,
        "trace_id": trace_id,
        "parent_event_id": parent_event_id,
        "actor": {
            "id": actor_id,
            "type": "human",
            # T0 for unknown/unclassified actors (Class C, D, or no tool_class);
            # T1 for identified Class A/B tools with a known process identity.
            "trust_tier": "T0" if (scan.tool_class or "A") in ("C", "D") or not scan.tool_name else "T1",
            "identity_confidence": min(1.0, scan.signals.identity) if scan.signals.identity > 0 else 0.5,
            "org_context": "unknown",
        },
        "endpoint": {
            "id": endpoint_id,
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "posture": "unmanaged",
        },
    }

    # Schema allows only A, B, C, D. Scanners like EvasionScanner may use "X"; normalize to schema enum.
    _SCHEMA_TOOL_CLASSES = frozenset({"A", "B", "C", "D"})
    tool_class = (
        scan.tool_class
        if (scan.tool_class and scan.tool_class in _SCHEMA_TOOL_CLASSES)
        else "A"
    )
    event["tool"] = {
        "name": scan.tool_name,
        "class": tool_class,
        "version": scan.tool_version,
        "attribution_confidence": confidence,
        "attribution_sources": scan.signals.active_layers(),
    }

    # Schema allows only: read, write, exec, network, repo, privileged, removal, observe.
    # Scanners may set policy-like values (e.g. approval_required, warn, none); normalize to schema enum.
    _SCHEMA_ACTION_TYPES = frozenset(
        {"read", "write", "exec", "network", "repo", "privileged", "removal", "observe"}
    )
    action_type = (
        scan.action_type
        if (scan.action_type and scan.action_type in _SCHEMA_ACTION_TYPES)
        else "observe"
    )
    risk_class = (
        scan.action_risk
        if (scan.action_risk and scan.action_risk in ("R1", "R2", "R3", "R4"))
        else "R1"
    )
    event["action"] = {
        "type": action_type,
        "risk_class": risk_class,
        "summary": scan.action_summary,
        "raw_ref": f"evidence://collector-scan/{scan.tool_name or 'unknown'}/{session_id}",
    }

    event["target"] = {
        "type": "host",
        "id": endpoint_id,
        "scope": "local endpoint",
        "sensitivity_tier": sensitivity,
    }

    if policy:
        event["policy"] = {
            "decision_state": policy.decision_state,
            "rule_id": policy.rule_id,
            "rule_version": policy.rule_version,
            "reason_codes": policy.reason_codes,
            "decision_confidence": policy.decision_confidence,
        }

    if enforcement:
        event["enforcement"] = {
            "tactic": enforcement.tactic,
            "success": enforcement.success,
            "detail": enforcement.detail,
            "simulated": enforcement.simulated,
            "allow_listed": enforcement.allow_listed,
            "rate_limited": getattr(enforcement, "rate_limited", False),
            "escalated": getattr(enforcement, "escalated", False),
        }
        if enforcement.simulated or enforcement.allow_listed or getattr(enforcement, "rate_limited", False):
            outcome_result = "simulated"
        else:
            outcome_result = "denied" if enforcement.success else "allowed"
        event["outcome"] = {
            "enforcement_result": outcome_result,
            "incident_flag": False,
            "incident_id": None,
        }

    severity_level = _compute_severity(confidence, scan.action_risk, sensitivity, policy)
    event["severity"] = {"level": severity_level}

    if correlation_context:
        event["correlation_context"] = {
            "multi_agent": True,
            "related_tool_names": correlation_context,
        }

    if trigger_context is not None:
        event["trigger_context"] = _trigger_context_to_dict(trigger_context)

    techniques = map_scan_result(scan)
    if techniques:
        event["mitre_attack"] = {"techniques": techniques}

    if session_timeline:
        event["session_timeline"] = session_timeline
    if timeline_summary:
        event["timeline_summary"] = timeline_summary

    if cross_tree_correlation is not None and isinstance(cross_tree_correlation, dict):
        event["cross_tree_correlation"] = cross_tree_correlation

    if possible_continuation is not None and isinstance(possible_continuation, dict):
        event_evidence["possible_continuation_of_fragment"] = possible_continuation
    if event_evidence:
        event["evidence_details"] = event_evidence

    if agent_status is not None and isinstance(agent_status, dict):
        event["agent_status"] = agent_status

    return event
