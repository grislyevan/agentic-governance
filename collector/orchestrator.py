"""Scan pipeline: one-cycle orchestration (scan, score, policy, enforce, emit).

This module runs a single collector cycle: start telemetry, run all scanners,
correlate, score confidence, evaluate policy, optionally enforce, and emit events.
The CLI entrypoint (main.py) invokes run_scan() for one-shot or daemon loop.

Sub-modules (extracted to reduce file size):
  event_builder   -- canonical event dict assembly and severity computation
  decision_engine -- credibility gating, session violation tracking
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

from config_loader import load_collector_config
from probe.models import TriggerContext

from engine.confidence import classify_confidence, compute_confidence
from engine.network import DEFAULT_ALLOWLIST_PATH, _matches_allowlist
from engine.session_timeline import build_session_timeline, timeline_summary_from_entries
from providers import get_best_provider
from telemetry.capabilities import get_capabilities_from_store, merge_capabilities
from telemetry.capability_drift import check_drift
from telemetry.event_store import EventStore
from engine.container import is_containerized as check_containerized
from engine.correlation import compute_correlation
from correlation import CorrelationHintsEngine, enrichment_for_tree
from scanner.process_tree import ProcessNode, build_trees, get_all_pids
from session.fragment_cache import FragmentCache, fragment_from_tree
from telemetry.diagnostics import DiagnosticsAccumulator
from engine.policy import (
    NetworkContext,
    PolicyDecision,
    apply_tamper_floor,
    evaluate_policy,
)
from enforcement.enforcer import Enforcer, EnforcementResult
from enforcement.approval_hold import ApprovalHoldManager, HoldConfig
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

# ---------------------------------------------------------------------------
# Re-exports from event_builder (backward compat for main.py, tests, patches)
# ---------------------------------------------------------------------------
from event_builder import (  # noqa: F401 – re-exported
    EVENT_VERSION,
    build_event,
)

# ---------------------------------------------------------------------------
# Re-exports from decision_engine (backward compat for tests)
# ---------------------------------------------------------------------------
from decision_engine import (  # noqa: F401 – re-exported
    EMISSION_MIN_CONFIDENCE,
    EMISSION_NO_SIGNALS_MAX_CONFIDENCE,
    SESSION_VIOLATION_TTL_SECONDS,
    _maybe_prune_violation_counts,
    _should_suppress_emission,
    _suppressed_reason,
    get_violation_count,
    record_violation,
)

# Import the session violation counts dict so orchestrator-level code can
# still reference it (tests may access it).
from decision_engine import _session_violation_counts  # noqa: F401

logger = logging.getLogger(__name__)

AnyEmitter = Union[EventEmitter, HttpEmitter, TcpEmitter]


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def explain_native_failure(provider_name: str, error: BaseException) -> str:
    """Return a short, readable explanation for native telemetry provider startup failure."""
    msg = str(error).strip() or type(error).__name__
    # Common patterns from ESF/ETW/eBPF helpers
    if "es_new_client" in msg or "esf_helper" in msg.lower() or "endpoint security" in msg.lower():
        return "Endpoint Security client initialization failed."
    if "entitlement" in msg.lower() or "permission" in msg.lower():
        return "Entitlement or permissions (e.g. Full Disk Access) required."
    if "not found" in msg.lower() or "no such file" in msg.lower():
        return "Helper binary or dependency not found."
    if msg:
        return msg[:200] if len(msg) > 200 else msg
    return f"{type(error).__name__} during startup"


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


def _load_network_allowlist(path: str | None) -> set[str] | None:
    """Load allowed destination hostnames/IPs from a newline-delimited file."""
    effective_path = path or DEFAULT_ALLOWLIST_PATH
    if not effective_path:
        return None
    p = Path(effective_path)
    try:
        entries = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                entries.add(line.lower())
        logger.debug("Loaded %d entries from network allowlist %s", len(entries), p)
        return entries
    except (FileNotFoundError, OSError):
        return None


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
            if host and not _matches_allowlist(addr=host, hostname=None, allowlist=allowlist):
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


def print_scan_summary(
    scan_summary: dict[str, list[dict[str, Any]]],
    telemetry_fidelity: str | None = None,
) -> None:
    """Print the Detec findings summary block (HIGH / MEDIUM / LOW / SUPPRESSED)."""
    has_any = any(scan_summary.get(k) for k in ("high", "medium", "low", "suppressed"))
    if not has_any:
        return
    print("\n================= Detec Findings =================")
    for level in ("high", "medium", "low"):
        entries = scan_summary.get(level, [])
        if not entries:
            continue
        label = level.upper()
        print(f"\n{label}")
        for e in entries:
            tool = e.get("tool") or "Unknown"
            tool_class = e.get("tool_class") or "A"
            policy = e.get("policy") or "observe"
            reason = e.get("reason") or ""
            print(f"  {tool} (Class {tool_class})")
            print(f"  Policy: {policy}")
            if reason:
                print(f"  Reason: {reason}")
    suppressed = scan_summary.get("suppressed", [])
    if suppressed:
        print("\nSUPPRESSED")
        for e in suppressed:
            tool = e.get("tool") or "Unknown"
            reason = e.get("reason") or "credibility gate"
            print(f"  {tool} – {reason}")
    if telemetry_fidelity:
        print(f"\nTelemetry fidelity: {telemetry_fidelity}")
    print("==================================================")


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


# ---------------------------------------------------------------------------
# Per-detection pipeline
# ---------------------------------------------------------------------------

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
    scan_summary: dict[str, list[dict[str, Any]]] | None = None,
    trigger_context: TriggerContext | None = None,
    session_timeline: list[dict[str, Any]] | None = None,
    cross_tree_correlation: dict[str, Any] | None = None,
    possible_continuation: dict[str, Any] | None = None,
    agent_status: dict[str, Any] | None = None,
    config: dict | None = None,
    pipe_server: Any = None,
) -> int:
    """Score, evaluate policy, enforce, and emit events for one detection."""
    events_emitted = 0

    confidence = compute_confidence(scan)
    conf_class = classify_confidence(confidence)

    if _should_suppress_emission(scan, confidence):
        if scan_summary is not None:
            scan_summary.setdefault("suppressed", []).append({
                "tool": scan.tool_name,
                "reason": _suppressed_reason(scan, confidence),
            })
        if verbose:
            print(f"  {scan.tool_name}: suppressed (credibility gate: confidence={confidence:.4f})")
        return 0

    pids = _extract_pids(scan)
    containerized = check_containerized(next(iter(pids))) if pids else None

    net_ctx = _build_network_context(scan, network_allowlist)

    _maybe_prune_violation_counts()
    _session_key = (endpoint_id, scan.tool_name or "unknown")
    _prior_violations = get_violation_count(_session_key)
    # Derive trust tier: T0 for unknown/autonomous actors (Class C/D or no process
    # name), T1 for identified Class A/B tools.
    _actor_trust_tier = (
        "T0"
        if (scan.tool_class or "A") in ("C", "D") or not scan.tool_name
        else "T1"
    )

    policy_decision = evaluate_policy(
        confidence=confidence,
        confidence_class=conf_class,
        tool_class=scan.tool_class or "A",
        sensitivity=sensitivity,
        action_risk=scan.action_risk,
        is_containerized=containerized,
        net_ctx=net_ctx,
        prior_violations=_prior_violations,
        actor_trust_tier=_actor_trust_tier,
    )
    if agent_status and agent_status.get("tamper_vectors"):
        policy_decision = apply_tamper_floor(
            policy_decision, agent_status["tamper_vectors"]
        )

    # Section 6.4: accumulate session violations for warn-or-higher decisions so
    # that repeat offenders are stepped up to approval_required on the next cycle.
    _VIOLATION_STATES = frozenset({"warn", "approval_required", "block"})
    if policy_decision.decision_state in _VIOLATION_STATES:
        record_violation(_session_key)

    if scan_summary is not None:
        bucket = conf_class.lower()
        scan_summary.setdefault(bucket, []).append({
            "tool": scan.tool_name,
            "tool_class": scan.tool_class or "A",
            "policy": policy_decision.decision_state,
            "reason": (scan.action_summary or "").strip() or policy_decision.rule_id or "detected",
        })

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
        correlation_context=correlation_context,
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

    if pipe_server and policy_decision.decision_state in ("detect", "warn", "block", "approval_required"):
        from collector.ipc.protocol import EVT_DETECTION, make_event
        pipe_server.broadcast(make_event(EVT_DETECTION, {
            "tool_name": scan.tool_name,
            "decision_state": policy_decision.decision_state,
            "confidence": confidence,
        }))

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
        trigger_context=trigger_context,
        session_timeline=session_timeline,
    )

    if verbose:
        print(f"  Emitting policy.evaluated event...")
    if emitter.emit(policy_event):
        events_emitted += 1

    should_enforce = False
    hold_result = None

    if enforcer:
        if policy_decision.decision_state == "block":
            should_enforce = True
        elif policy_decision.decision_state == "approval_required":
            # Hold enforcement: post to server and wait for analyst decision.
            hold_cfg_dict = (config or {}).get("approval_hold", {})
            hold_mgr = ApprovalHoldManager(
                api_url=(config or {}).get("api_url", ""),
                api_key=(config or {}).get("api_key", ""),
                config=HoldConfig.from_dict(hold_cfg_dict),
            )
            hold_result = hold_mgr.wait_for_decision(
                event_id=detection_event["event_id"],
                tool_name=scan.tool_name or "unknown",
                tool_class=scan.tool_class or "A",
                confidence_band=conf_class.lower(),
                confidence_score=confidence,
                policy_rule_id=policy_decision.rule_id,
                endpoint_id=endpoint_id,
            )
            # Only enforce (block) if denied; on approval, allow through.
            should_enforce = hold_result.decision == "denied"
            if verbose:
                outcome = "denied → enforcing" if should_enforce else "approved → allowing"
                print(f"  Approval hold resolved: {outcome} (timed_out={hold_result.timed_out})")

    if should_enforce and enforcer:
        network_elevated = "NET" in (policy_decision.rule_id or "")
        enf_result = enforcer.enforce(
            decision=policy_decision,
            tool_name=scan.tool_name or "unknown",
            tool_class=scan.tool_class or "A",
            pids=pids or None,
            network_elevated=network_elevated,
            process_patterns=scan.process_patterns,
        )
        # Propagate hold_effective from the approval hold result so the
        # enforcement event honestly reports whether processes were suspended
        # (SIGSTOP) during the approval period.  P4a: always False because
        # SIGSTOP is not yet implemented; P4b will set True on success.
        if hold_result is not None:
            enf_result.hold_effective = hold_result.hold_effective
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
            trigger_context=trigger_context,
            session_timeline=session_timeline,
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


# ---------------------------------------------------------------------------
# Main scan cycle
# ---------------------------------------------------------------------------

def run_scan(
    args: argparse.Namespace,
    emitter: AnyEmitter | None = None,
    state_differ: StateDiffer | None = None,
    posture_manager: PostureManager | None = None,
    enforcer: Enforcer | None = None,
    *,
    pipe_server: Any = None,
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
        enforcer = Enforcer(
            posture_manager=posture_mgr,
            dry_run=args.dry_run,
            allow_linux_uid_fallback=getattr(args, "allow_linux_uid_block_fallback", False),
        )

    network_allowlist = _load_network_allowlist(
        getattr(args, "network_allowlist_path", None)
    )

    on_alert = getattr(args, "_on_alert", None)
    collector_config = load_collector_config()
    event_store_cfg = collector_config.get("event_store") or {}
    event_store = EventStore(
        max_events=event_store_cfg.get("max_events", 10_000),
        retention_seconds=event_store_cfg.get("retention_seconds", 120.0),
        on_alert=on_alert,
        max_events_per_type=event_store_cfg.get("max_events_per_type"),
        rate_cap_per_second=event_store_cfg.get("rate_cap_per_second"),
        burst_window_seconds=event_store_cfg.get("burst_window_seconds"),
        max_events_per_burst=event_store_cfg.get("max_events_per_burst"),
    )
    provider = get_best_provider(getattr(args, "telemetry_provider", "auto"))
    sentinel = getattr(args, "sentinel", None) or {}
    trigger_context: TriggerContext | None = getattr(args, "_pending_trigger_context", None)
    if hasattr(args, "_pending_trigger_context"):
        setattr(args, "_pending_trigger_context", None)

    telemetry_fidelity: str | None = None
    try:
        if sentinel.get("enabled") and provider.name == "polling":
            from probe.engine import ProbeEngine
            probe_engine = ProbeEngine(
                endpoint_id=endpoint_id,
                probe_window_seconds=sentinel.get("observation_window_seconds", 120),
                cooldown_seconds=sentinel.get("trigger_cooldown_seconds", 10),
                max_alert_scans_per_minute=sentinel.get("max_alert_scans_per_minute", 4),
                max_elevations_per_5_minutes=sentinel.get("max_elevations_per_5_minutes", 10),
                on_request_scan=lambda ctx: (
                    setattr(args, "_pending_trigger_context", ctx),
                    (on_alert(ctx) if on_alert else None),
                )[1],
            )
            try:
                provider.start(
                    event_store,
                    sink=probe_engine,
                    probe_interval_ms=sentinel.get("probe_interval_ms", 1000),
                )
            except TypeError:
                provider.start(event_store)
        else:
            provider.start(event_store)
    except Exception as e:
        if provider.name != "polling":
            logger.debug(
                "Native provider %s failed to start; falling back to polling: %s",
                provider.name,
                e,
                exc_info=True,
            )
            reason = explain_native_failure(provider.name.upper(), e)
            print("Native telemetry provider (%s) failed to start." % provider.name.upper())
            print("Reason:")
            print("  %s" % reason)
            print("Falling back to polling provider.")
            print("Telemetry fidelity: DEGRADED")
            print("Polling mode may miss:")
            print("  - short-lived processes")
            print("  - file system events")
            print("  - fine-grained network correlation")
            from providers.polling import PollingProvider
            provider = PollingProvider()
            provider.start(event_store)
            telemetry_fidelity = "degraded (polling fallback)"
        else:
            raise

    if args.verbose:
        print(f"Collector session: {session_id}")
        print(f"Endpoint: {endpoint_id}  Actor: {actor_id}  Sensitivity: {sensitivity}")
        if telemetry_fidelity:
            print(f"Telemetry fidelity: {telemetry_fidelity}")
        if network_allowlist:
            print(f"Network allowlist: {len(network_allowlist)} entries")
        print("-" * 60)

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
    provider_cap = provider.capabilities()
    store_cap = get_capabilities_from_store(event_store)
    merged_capabilities = merge_capabilities(provider_cap, store_cap)
    capability_drift_list = check_drift(merged_capabilities)
    try:
        beh_scan = behavioral.scan(
            verbose=args.verbose,
            capabilities_override=merged_capabilities,
        )
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
    diagnostics_context = {
        "capability_drift": capability_drift_list if capability_drift_list else [],
        "provider_name": provider.name,
        "scan_failures": list(scan_failures),
    }
    ev_scan = None
    try:
        ev_scan = evasion.scan(
            verbose=args.verbose,
            diagnostics_context=diagnostics_context,
        )
        if ev_scan.detected:
            detected_scans.append(ev_scan)
            detected_tools.add("Evasion Detection")
    except Exception:
        logger.warning(
            "EvasionScanner raised an exception; treating as inconclusive",
            exc_info=True,
        )
        ev_scan = None

    tamper_vectors_list: list[str] = []
    if ev_scan and getattr(ev_scan, "detected", False) and ev_scan.evidence_details:
        tamper_vectors_list = [
            f["vector"]
            for f in ev_scan.evidence_details.get("evasion_findings", [])
            if isinstance(f, dict) and f.get("vector")
        ]
    if capability_drift_list:
        tamper_vectors_list.append("capability_drift")

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

    diagnostics = DiagnosticsAccumulator(rolling_scans=30)
    diagnostics.start_scan()

    trees = build_trees(event_store)
    hints_engine = CorrelationHintsEngine()
    correlation_hints_list = hints_engine.analyze(trees)
    cross_tree_by_scan: list[dict[str, Any] | None] = []
    repo_root_by_scan: list[str | None] = []
    fragment_cache = FragmentCache(retention_seconds=1800.0, max_fragments=500)
    for scan in detected_scans:
        pids = _extract_pids(scan)
        root_pid: int | None = None
        tree_for_scan: ProcessNode | None = None
        for tree in trees:
            if get_all_pids(tree) & pids:
                root_pid = tree.pid
                tree_for_scan = tree
                break
        if root_pid is not None:
            enr = enrichment_for_tree(root_pid, correlation_hints_list, tree=tree_for_scan)
            cross_tree_by_scan.append(enr)
        else:
            cross_tree_by_scan.append(None)
        frag = fragment_from_tree(tree_for_scan) if tree_for_scan else None
        repo_root_by_scan.append(frag.repo_root if frag else None)
    possible_continuation_by_scan: list[dict[str, Any] | None] = []
    now_ts = datetime.now(timezone.utc).timestamp()
    for i in range(len(detected_scans)):
        repo = repo_root_by_scan[i] if i < len(repo_root_by_scan) else None
        if not repo:
            possible_continuation_by_scan.append(None)
            continue
        continuations = fragment_cache.find_continuations(repo, now_ts, window_seconds=600.0)
        if not continuations:
            possible_continuation_by_scan.append(None)
            continue
        first = continuations[0]
        possible_continuation_by_scan.append({
            "first_seen": first.first_seen,
            "patterns": first.patterns[:5],
            "sensitive_paths": first.sensitive_paths[:3],
        })

    scan_timelines: list[list[dict[str, str]]] = []
    for scan in detected_scans:
        pids = _extract_pids(scan)
        timeline = build_session_timeline(
            event_store, scan.tool_name or "", pids, expand_tree=True
        )
        scan_timelines.append(timeline)

    if getattr(args, "session_report", False):
        from session_report import build_session_reports, format_session_report_for_cli
        for report in build_session_reports(
            event_store, detected_scans, tool_timelines=scan_timelines
        ):
            print(format_session_report_for_cli(report))
            print("")

    scan_summary: dict[str, list[dict[str, Any]]] = {
        "high": [],
        "medium": [],
        "low": [],
        "suppressed": [],
    }
    pattern_ids: list[str] = []
    for scan in detected_scans:
        for p in (scan.evidence_details.get("behavioral_patterns") or []):
            if isinstance(p, dict) and p.get("pattern_id"):
                pattern_ids.append(p["pattern_id"])
    diagnostics.end_scan(trees_count=len(trees), patterns_triggered=pattern_ids)
    event_counts = event_store.get_event_counts()
    agent_status = diagnostics.get_status(
        provider_name=provider.name,
        event_counts=event_counts,
        capability_drift=capability_drift_list if capability_drift_list else None,
        tamper_vectors=tamper_vectors_list if tamper_vectors_list else None,
    )

    total_events = 0
    for i, scan in enumerate(detected_scans):
        related = correlation_map.get(scan.tool_name or "", [])
        session_timeline = scan_timelines[i] if i < len(scan_timelines) else None
        cross_tree = cross_tree_by_scan[i] if i < len(cross_tree_by_scan) else None
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
            scan_summary=scan_summary,
            trigger_context=trigger_context,
            session_timeline=session_timeline,
            cross_tree_correlation=cross_tree,
            possible_continuation=possible_continuation_by_scan[i] if i < len(possible_continuation_by_scan) else None,
            agent_status=agent_status,
            config=collector_config,
            pipe_server=pipe_server,
        )

    for tree in trees:
        fragment_cache.record_tree(tree)

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
            trigger_context=trigger_context,
        )

    provider.stop()

    print_scan_summary(scan_summary, telemetry_fidelity)

    stats = emitter.stats
    if args.verbose:
        print(f"\n{'=' * 60}")
    print(f"Scan complete. Events emitted: {stats['emitted']}, "
          f"validation failures: {stats['failed']}")
    if own_emitter and not args.dry_run:
        print(f"Output: {args.output}")

    return 0 if stats["failed"] == 0 else 1
