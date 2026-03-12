"""CLI entrypoint: runs scans, scores confidence, evaluates policy, emits events.

One-shot mode (default):
    python -m collector.main --dry-run

Daemon mode (persistent endpoint agent):
    python -m collector.main \\
        --api-url http://localhost:8000/api \\
        --api-key <key> \\
        --interval 300 \\
        --report-all          # omit to report changes only
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import platform
import signal
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

# Ensure collector sub-packages are importable regardless of invocation method
# (python main.py from collector/, python -m collector.main from project root, etc.)
_COLLECTOR_DIR = str(Path(__file__).resolve().parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from config_loader import argparse_defaults
from engine.confidence import classify_confidence, compute_confidence
from providers import get_best_provider
from telemetry.event_store import EventStore
from engine.container import is_containerized as check_containerized
from engine.policy import NetworkContext, PolicyDecision, evaluate_policy
from enforcement.enforcer import Enforcer, EnforcementResult
from enforcement.posture import PostureManager
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from agent.state import StateDiffer
from scanner.base import ScanResult
from scanner.ai_extensions import AIExtensionScanner
from scanner.aider import AiderScanner
from scanner.claude_code import ClaudeCodeScanner
from scanner.cline import ClineScanner
from scanner.continue_ext import ContinueScanner
from scanner.copilot import CopilotScanner
from scanner.cursor import CursorScanner
from scanner.gpt_pilot import GPTPilotScanner
from scanner.lm_studio import LMStudioScanner
from scanner.ollama import OllamaScanner
from scanner.open_interpreter import OpenInterpreterScanner
from scanner.behavioral import BehavioralScanner
from scanner.openclaw import OpenClawScanner

logger = logging.getLogger(__name__)

AnyEmitter = Union[EventEmitter, HttpEmitter, TcpEmitter]

# Version map — keeps collector artifacts aligned with the Playbook.
#   Playbook  0.4   →  RULE_VERSION 0.4.0, EVENT_VERSION 0.4.0
#   API               has its own versioning cadence (currently 0.1.0)
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
    """Pull process IDs from scan evidence for enforcement targeting.

    Handles both int and string PIDs since some scanners store pgrep
    output as strings.
    """
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
    """Load allowed destination hostnames/IPs from a newline-delimited file.

    Returns an empty set when path is None or the file is missing, which
    disables network policy evaluation (net_ctx stays None).
    """
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
    """Build a NetworkContext from scan evidence and the allowlist.

    Returns None when the allowlist is empty (opt-in: no allowlist means
    network policy rules are skipped, preserving default behavior).
    """
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

    event["tool"] = {
        "name": scan.tool_name,
        "class": scan.tool_class,
        "version": scan.tool_version,
        "attribution_confidence": confidence,
        "attribution_sources": scan.signals.active_layers(),
    }

    event["action"] = {
        "type": scan.action_type,
        "risk_class": scan.action_risk,
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
    """Run all scanners and partition results into detections vs failures.

    Returns (detected_scans, detected_tool_names, scan_failure_names).
    """
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
) -> int:
    """Score, evaluate policy, enforce, and emit events for one detection.

    Returns the number of events successfully emitted.
    """
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
    """Emit detection.cleared for tools that vanished since the last cycle.

    Tools whose scanners failed are excluded: a crash is not "cleared."
    """
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
    """Execute the full scan pipeline.

    Stages:
      1. _collect_scan_results  - run scanners, partition into detections/failures
      2. _process_detection     - score, evaluate, enforce, emit per detection
      3. _emit_cleared_events   - handle tools that vanished since the last cycle

    When *emitter* is None the function creates a local EventEmitter
    (one-shot mode).  When provided (daemon mode) it uses the caller-
    supplied emitter and optionally a StateDiffer to suppress unchanged
    detections.  When *posture_manager* and *enforcer* are provided (daemon
    mode), they are reused; otherwise new instances are created per run.
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

    # Create event store and start telemetry provider.
    # In daemon mode the alert callback is attached so native providers
    # can wake the scan loop for out-of-cycle scans.
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

    # Poll telemetry before scan (PollingProvider populates event store on-demand)
    if hasattr(provider, "poll"):
        provider.poll()

    # Stage 1: collect from named scanners
    detected_scans, detected_tools, scan_failures = _collect_scan_results(
        scanners, args.verbose,
    )

    # Stage 1b: behavioral scanner runs after named scanners with PID dedup
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

    # Stage 2: process each detection
    total_events = 0
    for scan in detected_scans:
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
        )

    # Stage 3: cleared events
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


# ---------------------------------------------------------------------------
# Daemon helpers
# ---------------------------------------------------------------------------

def _heartbeat_loop(
    emitter: HttpEmitter | TcpEmitter,
    hostname: str,
    interval: int,
    stop_event: threading.Event,
    telemetry_provider: str = "polling",
) -> None:
    """Background thread: send heartbeats every interval seconds."""
    while not stop_event.wait(timeout=interval):
        emitter.heartbeat(
            hostname=hostname,
            interval_seconds=interval,
            telemetry_provider=telemetry_provider,
        )


def _build_lifecycle_event(
    event_type: str,
    endpoint_id: str,
    actor_id: str,
    summary: str,
) -> dict[str, Any]:
    """Build a lightweight lifecycle event (heartbeat/shutdown)."""
    now = datetime.now(timezone.utc).isoformat()
    session_id = str(uuid.uuid4())
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "event_version": EVENT_VERSION,
        "observed_at": now,
        "ingested_at": now,
        "session_id": session_id,
        "trace_id": f"trace-lifecycle-{session_id[:8]}",
        "parent_event_id": None,
        "actor": {
            "id": actor_id,
            "type": "automation",
            "trust_tier": "T1",
            "identity_confidence": 1.0,
            "org_context": "unknown",
        },
        "endpoint": {
            "id": endpoint_id,
            "os": f"{platform.system()} {platform.release()} {platform.machine()}",
            "posture": "unmanaged",
        },
        "action": {
            "type": "exec",
            "risk_class": "R1",
            "summary": summary,
            "raw_ref": f"evidence://collector-lifecycle/{endpoint_id}/{session_id}",
        },
        "target": {
            "type": "host",
            "id": endpoint_id,
            "scope": "local endpoint",
            "sensitivity_tier": "Tier0",
        },
        "tool": {
            "name": "agentic-gov-collector",
            "class": "A",
            "version": EVENT_VERSION,
            "attribution_confidence": 1.0,
            "attribution_sources": ["process"],
        },
        "severity": {"level": "S0"},
    }


_PID_DIR = Path.home() / ".agentic-gov"
_PID_FILE = _PID_DIR / "agent.pid"


def _write_pid_file() -> None:
    _PID_DIR.mkdir(parents=True, exist_ok=True)
    _PID_FILE.write_text(str(os.getpid()))


def _remove_pid_file() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def _run_daemon(args: argparse.Namespace) -> None:
    """Run the collector as a persistent daemon until SIGINT/SIGTERM."""
    if _PID_FILE.exists():
        try:
            old_pid = int(_PID_FILE.read_text().strip())
            os.kill(old_pid, 0)
            print(
                f"Another agent instance appears to be running (PID {old_pid}). "
                f"Remove {_PID_FILE} if this is stale.",
                file=sys.stderr,
            )
            sys.exit(1)
        except (ProcessLookupError, ValueError, OSError):
            pass

    _write_pid_file()

    from enforcement.cleanup import cleanup_orphaned_rules
    cleanup_orphaned_rules()

    hostname = args.endpoint_id
    protocol = getattr(args, "protocol", "http")

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
    enforcer = Enforcer(posture_manager=posture_mgr, dry_run=args.dry_run)

    def _on_posture(
        posture: str,
        auto_enforce_threshold: float | None = None,
        allow_list: list[str] | None = None,
        llm_hosts: list[str] | None = None,
    ) -> None:
        posture_mgr.update(
            posture,
            auto_enforce_threshold=auto_enforce_threshold,
            allow_list=allow_list,
            source="server_push",
        )
        if llm_hosts:
            from scanner.behavioral_patterns import update_llm_hosts
            update_llm_hosts(set(llm_hosts))

    if protocol == "tcp":
        gateway_host = getattr(args, "gateway_host", None)
        gateway_port = getattr(args, "gateway_port", 8001)

        if not gateway_host:
            from urllib.parse import urlparse
            parsed = urlparse(args.api_url)
            gateway_host = parsed.hostname or "localhost"

        auto_tls = args.api_url.startswith("https://") if args.api_url else False
        tls_enabled = getattr(args, "tls", auto_tls)
        if not tls_enabled and auto_tls:
            tls_enabled = True
        if not tls_enabled and args.api_url and not args.api_url.startswith("http://localhost"):
            logger.warning(
                "TCP transport running without TLS. Set --tls or use https:// API URL "
                "to enable encrypted transport."
            )

        emitter = TcpEmitter(
            gateway_host=gateway_host,
            gateway_port=gateway_port,
            api_key=args.api_key,
            hostname=hostname,
            agent_version=EVENT_VERSION,
            tls=tls_enabled,
            on_posture=_on_posture,
        )
    else:
        emitter = HttpEmitter(
            api_url=args.api_url,
            api_key=args.api_key,
            on_posture=_on_posture,
        )

    differ = StateDiffer(report_all=args.report_all)

    stop_event = threading.Event()

    # Alert-triggered scan: when a native provider pushes a high-priority
    # process exec event, this Event is set so the loop wakes early.
    scan_trigger = threading.Event()

    def _on_alert(event: object) -> None:
        logger.info("Alert-triggered scan requested (pid=%s)", getattr(event, "pid", "?"))
        scan_trigger.set()

    # Stash the callback so run_scan can wire it into the EventStore.
    args._on_alert = _on_alert  # type: ignore[attr-defined]

    def _handle_signal(signum: int, frame: Any) -> None:
        print(f"\nReceived signal {signum}, shutting down daemon...", file=sys.stderr)
        stop_event.set()
        scan_trigger.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except (ValueError, OSError):
        pass

    telemetry_preference = getattr(args, "telemetry_provider", "auto")
    resolved_provider = get_best_provider(telemetry_preference)
    telemetry_provider_name = resolved_provider.name

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(emitter, hostname, args.interval, stop_event, telemetry_provider_name),
        daemon=True,
        name="heartbeat",
    )
    heartbeat_thread.start()

    print(
        f"Agentic-gov endpoint agent started — "
        f"interval={args.interval}s  api={args.api_url}  "
        f"mode={'report-all' if args.report_all else 'changes-only'}",
        file=sys.stderr,
    )

    while not stop_event.is_set():
        flushed = emitter.flush_buffer()
        if flushed and args.verbose:
            print(f"Flushed {flushed} buffered events")

        triggered = scan_trigger.is_set()
        scan_trigger.clear()
        scan_source = "alert-triggered" if triggered else "scheduled"
        logger.info("Starting %s scan cycle", scan_source)

        run_scan(
            args,
            emitter=emitter,
            state_differ=differ,
            posture_manager=posture_mgr,
            enforcer=enforcer,
        )

        # Wait for the interval OR an alert, whichever comes first.
        # If stop_event fires, the outer loop condition exits.
        scan_trigger.wait(timeout=args.interval)
        if stop_event.is_set():
            break

    shutdown_event = _build_lifecycle_event(
        event_type="agent.shutdown",
        endpoint_id=hostname,
        actor_id=args.actor_id,
        summary="Collector agent shutting down gracefully",
    )
    emitter.emit(shutdown_event)

    if isinstance(emitter, TcpEmitter):
        emitter.shutdown()

    stop_event.set()
    cleanup_orphaned_rules()
    _remove_pid_file()
    print("Agentic-gov endpoint agent stopped.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Endpoint telemetry collector for agentic AI tool detection",
    )
    parser.add_argument(
        "--output",
        help="Output file for NDJSON events (default: ./scan-results.ndjson)",
    )
    parser.add_argument(
        "--endpoint-id",
        help="Endpoint identifier (default: hostname)",
    )
    parser.add_argument(
        "--actor-id",
        help="Actor/user identifier (default: current OS user)",
    )
    parser.add_argument(
        "--sensitivity",
        choices=["Tier0", "Tier1", "Tier2", "Tier3"],
        help="Asset sensitivity tier (default: Tier0)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=None,
        help="Print events to stdout instead of writing to file",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=None,
        help="Print detailed scan progress",
    )
    parser.add_argument(
        "--interval", type=int, metavar="SECONDS",
        help="Run as persistent daemon, scanning every N seconds (0 = one-shot)",
    )
    parser.add_argument(
        "--api-url", metavar="URL",
        help="Central API base URL, e.g. http://localhost:8000/api",
    )
    parser.add_argument(
        "--api-key", metavar="KEY",
        help="API key for authenticating with the central server",
    )
    parser.add_argument(
        "--report-all", action="store_true", default=None,
        help="Report all detections every cycle (default: changes only)",
    )
    parser.add_argument(
        "--posture", dest="enforcement_posture",
        choices=["passive", "audit", "active"],
        help="Enforcement posture (default: passive, or as set by central server)",
    )
    parser.add_argument(
        "--enforce", action="store_true", default=False,
        help="[DEPRECATED] Use --posture active instead",
    )
    parser.add_argument(
        "--auto-enforce-threshold", dest="auto_enforce_threshold",
        type=float, metavar="SCORE",
        help="Minimum confidence for auto-enforcement in active posture (default: 0.75)",
    )
    parser.add_argument(
        "--protocol", choices=["http", "tcp"], default="http",
        help="Transport protocol for daemon mode (default: http)",
    )
    parser.add_argument(
        "--gateway-host", dest="gateway_host", metavar="HOST",
        help="Gateway host for TCP protocol (default: derived from --api-url)",
    )
    parser.add_argument(
        "--gateway-port", dest="gateway_port", type=int, default=8001,
        help="Gateway port for TCP protocol (default: 8001)",
    )
    parser.add_argument(
        "--telemetry-provider",
        choices=["auto", "native", "polling"],
        default="auto",
        help="Telemetry provider preference (default: auto)",
    )

    # Centralized config: code defaults < config file < env vars < CLI
    parser.set_defaults(**argparse_defaults())

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.interval > 0:
        if not args.api_url or not args.api_key:
            parser.error("--interval requires both --api-url and --api-key")
        _run_daemon(args)
    else:
        sys.exit(run_scan(args))


if __name__ == "__main__":
    main()
