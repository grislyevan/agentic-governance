"""Scan pipeline: one-cycle orchestration (scan, score, policy, enforce, emit).

This module runs a single collector cycle: start telemetry, run all scanners,
correlate, score confidence, evaluate policy, optionally enforce, and emit events.
The CLI entrypoint (main.py) invokes run_scan() for one-shot or daemon loop.
"""

from __future__ import annotations

import argparse
import logging
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from engine.attack_mapping import map_scan_result
from engine.confidence import classify_confidence, compute_confidence
from providers import get_best_provider
from telemetry.event_store import EventStore
from engine.container import is_containerized as check_containerized
from engine.correlation import compute_correlation
from engine.policy import NetworkContext, PolicyDecision, evaluate_policy
from enforcement.enforcer import Enforcer, EnforcementResult
from enforcement.posture import PostureManager
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from agent.state import StateDiffer
from scanner.base import LayerSignals, ScanResult
from scanner.scheduler_artifacts import get_scheduler_evidence_by_tool
from scanner.ai_extensions import AIExtensionScanner
from scanner.aider import AiderScanner
from scanner.claude_code import ClaudeCodeScanner
from scanner.claude_cowork import ClaudeCoworkScanner
from scanner.cline import ClineScanner
from scanner.continue_ext import ContinueScanner
from scanner.copilot import CopilotScanner
from scanner.cursor import CursorScanner
from scanner.gpt_pilot import GPTPilotScanner
from scanner.lm_studio import LMStudioScanner
from scanner.ollama import OllamaScanner
from scanner.open_interpreter import OpenInterpreterScanner
from scanner.behavioral import BehavioralScanner
from scanner.evasion import EvasionScanner
from scanner.mcp import MCPScanner
from scanner.openclaw import OpenClawScanner

logger = logging.getLogger(__name__)

AnyEmitter = Union[EventEmitter, HttpEmitter, TcpEmitter]

# Version map: Playbook 0.4 -> EVENT_VERSION 0.4.0
EVENT_VERSION = "0.4.0"


def _normalize_pid(value: object) -> int | None:
    """Coerce a PID from int or numeric string, returning None if invalid."""
    if isinstance(value, int):
        return value if value > 1 else None
    if isinstance(value, str) and value.strip().isdigit():
        pid = int(value.strip())
        return pid if pid > 1 else None
    return None


def _extract_pids(scan: ScanResult) -> set[int]:
    """Pull process IDs from scan evidence for enforcement targeting."""
    pids: set[int] = set()
    for entry in scan.evidence_details.get("process_entries", []):
        pid = _normalize_pid(entry.get("pid"))
        if pid is not None:
            pids.add(pid)
    for key in ("listener_pid", "ipykernel_pid"):
        pid = _normalize_pid(scan.evidence_details.get(key))
        if pid is not None:
            pids.add(pid)
    return pids


def _load_network_allowlist(path: str | None) -> set[str]:
    """Load allowed destination hostnames/IPs from a newline-delimited file."""
    if not path:
        return set()
    p = Path(path)
    if not p.is_file():
        logger.warning("Network allowlist file not found: %s", p)
        return set()
    try:
        entries = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(line.lower())
        logger.debug("Loaded %d entries from network allowlist %s", len(entries), p)
        return entries
    except OSError as exc:
        logger.warning("Could not read network allowlist %s: %s", p, exc)
        return set()


def _build_network_context(
    scan: ScanResult,
    allowlist: set[str],
) -> NetworkContext | None:
    """Build a NetworkContext from scan evidence and the allowlist."""
    if not allowlist:
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
            if host and host not in allowlist:
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
) -> dict[str, Any]:
    """Construct a canonical event dict conforming to the JSON Schema."""
    now = datetime.now(timezone.utc).isoformat()

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
            "trust_tier": "T1",
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

    techniques = map_scan_result(scan)
    if techniques:
        event["mitre_attack"] = {"techniques": techniques}

    return event


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


def _collect_scan_results(
    scanners: list[Any],
    verbose: bool,
) -> tuple[list[ScanResult], set[str], set[str]]:
    """Run all scanners and partition results into detections vs failures."""
    detected: list[ScanResult] = []
    detected_names: set[str] = set()
    failures: set[str] = set()

    for scanner in scanners:
        if verbose:
            print(f"\n--- Scanning for {scanner.tool_name} ---")

        try:
            scan = scanner.scan(verbose=verbose)
        except Exception:
            logger.warning(
                "Scanner %s raised an exception; treating as inconclusive",
                scanner.tool_name,
                exc_info=True,
            )
            failures.add(scanner.tool_name)
            continue

        if not scan.detected:
            if verbose:
                print(f"  {scanner.tool_name}: Not detected")
            continue

        detected.append(scan)
        detected_names.add(scan.tool_name)

    return detected, detected_names, failures


def _process_detection(
    scan: ScanResult,
    *,
    sensitivity: str,
    endpoint_id: str,
    actor_id: str,
    session_id: str,
    trace_id: str,
    emitter: AnyEmitter,
    enforcer: Enforcer | None,
    state_differ: StateDiffer | None,
    network_allowlist: set[str] | None = None,
    verbose: bool,
    correlation_context: list[str] | None = None,
) -> int:
    """Score, evaluate policy, enforce, and emit events for one detection."""
    events_emitted = 0

    confidence = compute_confidence(scan)
    conf_class = classify_confidence(confidence)

    pids = _extract_pids(scan)
    containerized = check_containerized(next(iter(pids))) if pids else None

    net_ctx = _build_network_context(scan, network_allowlist or set())

    policy_decision = evaluate_policy(
        confidence=confidence,
        confidence_class=conf_class,
        tool_class=scan.tool_class or "A",
        sensitivity=sensitivity,
        action_risk=scan.action_risk,
        is_containerized=containerized,
        net_ctx=net_ctx,
    )

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
        print(f"  Signals — P:{scan.signals.process:.2f} F:{scan.signals.file:.2f} "
              f"N:{scan.signals.network:.2f} I:{scan.signals.identity:.2f} "
              f"B:{scan.signals.behavior:.2f}")
        if scan.penalties:
            print(f"  Penalties: {scan.penalties}")
        if scan.evasion_boost > 0:
            print(f"  Evasion boost: +{scan.evasion_boost:.2f}")

    detection_event = build_event(
        event_type="detection.observed",
        endpoint_id=endpoint_id,
        actor_id=actor_id,
        session_id=session_id,
        trace_id=trace_id,
        scan=scan,
        confidence=confidence,
        sensitivity=sensitivity,
        correlation_context=correlation_context,
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

    if verbose:
        print(f"  Policy: {policy_decision.decision_state} "
              f"(rule={policy_decision.rule_id})")

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
        correlation_context=correlation_context,
    )

    if verbose:
        print(f"  Emitting policy.evaluated event...")
    if emitter.emit(policy_event):
        events_emitted += 1

    if enforcer and policy_decision.decision_state in ("block", "approval_required"):
        network_elevated = "NET" in (policy_decision.rule_id or "")
        enf_result = enforcer.enforce(
            decision=policy_decision,
            tool_name=scan.tool_name or "unknown",
            tool_class=scan.tool_class or "A",
            pids=pids or None,
            network_elevated=network_elevated,
            process_patterns=scan.process_patterns,
        )
        if verbose:
            tag = "AUDIT" if enf_result.simulated else "LIVE"
            print(f"  Enforcement [{tag}]: {enf_result.tactic} "
                  f"({'OK' if enf_result.success else 'FAILED'}) "
                  f"- {enf_result.detail}")

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
        )
        if verbose:
            print(f"  Emitting {event_type} event...")
        if emitter.emit(enforcement_event):
            events_emitted += 1

    return events_emitted


def _emit_cleared_events(
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
        )
        if emitter.emit(cleared_event):
            events_emitted += 1
        state_differ.mark_cleared(tool_name)
    return events_emitted


def run_scan(
    args: argparse.Namespace,
    emitter: AnyEmitter | None = None,
    state_differ: StateDiffer | None = None,
    posture_manager: PostureManager | None = None,
    enforcer: Enforcer | None = None,
) -> int:
    """Execute one full scan cycle: telemetry, scanners, score, policy, enforce, emit.

    When emitter is None the function creates a local EventEmitter (one-shot).
    When provided (daemon mode) it uses the caller-supplied emitter and optionally
    StateDiffer to suppress unchanged detections.
    """
    session_id = str(uuid.uuid4())
    trace_id = f"trace-collector-{session_id[:8]}"
    endpoint_id = args.endpoint_id
    actor_id = args.actor_id
    sensitivity = args.sensitivity
    own_emitter = emitter is None

    if own_emitter:
        emitter = EventEmitter(output_path=args.output, dry_run=args.dry_run)

    if posture_manager is None:
        posture_mgr = PostureManager(
            initial_posture=getattr(args, "enforcement_posture", "passive"),
            initial_threshold=getattr(args, "auto_enforce_threshold", 0.75),
        )
        if getattr(args, "enforce", False):
            import warnings
            warnings.warn(
                "--enforce is deprecated and will be removed in a future release. "
                "Use --posture active instead, or set posture from the central server.",
                DeprecationWarning,
                stacklevel=2,
            )
            posture_mgr.update("active", source="cli_override")
        elif "--posture" in sys.argv:
            posture_mgr.update(
                getattr(args, "enforcement_posture", "passive"),
                source="cli_override",
            )
    else:
        posture_mgr = posture_manager

    if enforcer is None:
        enforcer = Enforcer(posture_manager=posture_mgr, dry_run=args.dry_run)

    network_allowlist = _load_network_allowlist(
        getattr(args, "network_allowlist_path", None)
    )

    if args.verbose:
        print(f"Collector session: {session_id}")
        print(f"Endpoint: {endpoint_id}  Actor: {actor_id}  Sensitivity: {sensitivity}")
        if network_allowlist:
            print(f"Network allowlist: {len(network_allowlist)} entries")
        print("-" * 60)

    on_alert = getattr(args, "_on_alert", None)
    event_store = EventStore(on_alert=on_alert)
    provider = get_best_provider(getattr(args, "telemetry_provider", "auto"))
    try:
        provider.start(event_store)
    except Exception:
        if provider.name != "polling":
            logger.warning(
                "Native provider %s failed to start; falling back to polling",
                provider.name,
                exc_info=True,
            )
            from providers.polling import PollingProvider
            provider = PollingProvider()
            provider.start(event_store)
        else:
            raise

    scanners = [
        ClaudeCodeScanner(event_store=event_store),
        ClaudeCoworkScanner(event_store=event_store),
        OllamaScanner(event_store=event_store),
        CursorScanner(event_store=event_store),
        CopilotScanner(event_store=event_store),
        OpenInterpreterScanner(event_store=event_store),
        OpenClawScanner(event_store=event_store),
        AiderScanner(event_store=event_store),
        LMStudioScanner(event_store=event_store),
        ContinueScanner(event_store=event_store),
        GPTPilotScanner(event_store=event_store),
        ClineScanner(event_store=event_store),
        AIExtensionScanner(event_store=event_store),
    ]

    if hasattr(provider, "poll"):
        provider.poll()

    detected_scans, detected_tools, scan_failures = _collect_scan_results(
        scanners, args.verbose,
    )

    named_pids: set[int] = set()
    for scan in detected_scans:
        named_pids.update(_extract_pids(scan))

    behavioral = BehavioralScanner(event_store=event_store, exclude_pids=named_pids)
    try:
        beh_scan = behavioral.scan(verbose=args.verbose)
        if beh_scan.detected:
            detected_scans.append(beh_scan)
            detected_tools.add(beh_scan.tool_name or "Unknown Agent")
    except Exception:
        logger.warning(
            "BehavioralScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )
        scan_failures.add("Unknown Agent")

    evasion = EvasionScanner(event_store=event_store)
    try:
        ev_scan = evasion.scan(verbose=args.verbose)
        if ev_scan.detected:
            detected_scans.append(ev_scan)
            detected_tools.add("Evasion Detection")
    except Exception:
        logger.warning(
            "EvasionScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )

    mcp = MCPScanner(event_store=event_store)
    try:
        mcp_scan = mcp.scan(verbose=args.verbose)
        if mcp_scan.detected:
            detected_scans.append(mcp_scan)
            detected_tools.add("MCP Infrastructure")
    except Exception:
        logger.warning(
            "MCPScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )

    try:
        scheduler_by_tool = get_scheduler_evidence_by_tool()
        for scan in detected_scans:
            evidence_list = scheduler_by_tool.get(scan.tool_name or "")
            if not evidence_list:
                continue
            scan.evidence_details.setdefault("scheduler_entries", []).extend(evidence_list)
            current = scan.signals.file
            scan.signals.file = min(1.0, current + 0.15)
            if args.verbose:
                print(f"  Scheduler artifact for {scan.tool_name}: {len(evidence_list)} entry(ies)")
        for tool_name, evidence_list in scheduler_by_tool.items():
            if tool_name in detected_tools:
                continue
            first = evidence_list[0]
            tool_class = first.get("tool_class", "C")
            new_scan = ScanResult(
                detected=True,
                tool_name=tool_name,
                tool_class=tool_class,
                signals=LayerSignals(file=0.5, process=0.0, network=0.0, identity=0.0, behavior=0.0),
                evidence_details={"scheduler_entries": list(evidence_list)},
                action_summary=f"Scheduled execution (cron/LaunchAgent): {len(evidence_list)} entry(ies)",
            )
            detected_scans.append(new_scan)
            detected_tools.add(tool_name)
            if args.verbose:
                print(f"  Scheduler-only detection: {tool_name} ({len(evidence_list)} entry(ies))")
    except Exception:
        logger.warning(
            "Scheduler artifact scan raised an exception; skipping",
            exc_info=True,
        )

    correlation_map = compute_correlation(detected_scans, event_store, _extract_pids)

    total_events = 0
    for scan in detected_scans:
        related = correlation_map.get(scan.tool_name or "", [])
        total_events += _process_detection(
            scan,
            sensitivity=sensitivity,
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            emitter=emitter,
            enforcer=enforcer,
            state_differ=state_differ,
            network_allowlist=network_allowlist or None,
            verbose=args.verbose,
            correlation_context=related if related else None,
        )

    if state_differ is not None:
        total_events += _emit_cleared_events(
            state_differ,
            detected_tools,
            scan_failures,
            endpoint_id=endpoint_id,
            actor_id=actor_id,
            session_id=session_id,
            trace_id=trace_id,
            sensitivity=sensitivity,
            emitter=emitter,
            verbose=args.verbose,
        )

    provider.stop()

    stats = emitter.stats
    if args.verbose:
        print(f"\n{'=' * 60}")
    print(f"Scan complete. Events emitted: {stats['emitted']}, "
          f"validation failures: {stats['failed']}")
    if own_emitter and not args.dry_run:
        print(f"Output: {args.output}")

    return 0 if stats["failed"] == 0 else 1
