"""CLI entrypoint: runs scans, scores confidence, evaluates policy, emits events.

One-shot mode (default):
    python -m collector.main --dry-run

Daemon mode (persistent endpoint agent):
    python -m collector.main \\
        --api-url http://localhost:8000 \\
        --api-key <key> \\
        --interval 300 \\
        --report-all          # omit to report changes only
"""

from __future__ import annotations

import argparse
import getpass
import logging
import platform
import signal
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Union

from engine.confidence import classify_confidence, compute_confidence
from engine.policy import PolicyDecision, evaluate_policy
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from agent.state import StateDiffer
from scanner.base import ScanResult
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
from scanner.openclaw import OpenClawScanner

AnyEmitter = Union[EventEmitter, HttpEmitter]

EVENT_VERSION = "0.2.0"


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


def run_scan(
    args: argparse.Namespace,
    emitter: AnyEmitter | None = None,
    state_differ: StateDiffer | None = None,
) -> int:
    """Execute the full scan pipeline.

    When *emitter* is None the function creates a local EventEmitter
    (one-shot mode).  When provided (daemon mode) it uses the caller-
    supplied emitter and optionally a StateDiffer to suppress unchanged
    detections.
    """
    session_id = str(uuid.uuid4())
    trace_id = f"trace-collector-{session_id[:8]}"
    endpoint_id = args.endpoint_id
    actor_id = args.actor_id
    sensitivity = args.sensitivity
    own_emitter = emitter is None

    if own_emitter:
        emitter = EventEmitter(output_path=args.output, dry_run=args.dry_run)

    if args.verbose:
        print(f"Collector session: {session_id}")
        print(f"Endpoint: {endpoint_id}  Actor: {actor_id}  Sensitivity: {sensitivity}")
        print("-" * 60)

    scanners = [
        ClaudeCodeScanner(),
        OllamaScanner(),
        CursorScanner(),
        CopilotScanner(),
        OpenInterpreterScanner(),
        OpenClawScanner(),
        AiderScanner(),
        LMStudioScanner(),
        ContinueScanner(),
        GPTPilotScanner(),
        ClineScanner(),
    ]
    total_events = 0
    detected_tools: set[str] = set()

    for scanner in scanners:
        if args.verbose:
            print(f"\n--- Scanning for {scanner.tool_name} ---")

        scan = scanner.scan(verbose=args.verbose)

        if not scan.detected:
            if args.verbose:
                print(f"  {scanner.tool_name}: Not detected")
            continue

        detected_tools.add(scan.tool_name)
        confidence = compute_confidence(scan)
        conf_class = classify_confidence(confidence)
        policy_decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=scan.tool_class or "A",
            sensitivity=sensitivity,
            action_risk=scan.action_risk,
        )

        # In daemon mode, skip if nothing material changed
        if state_differ is not None:
            changed, reasons = state_differ.is_changed(
                tool_name=scan.tool_name,
                tool_class=scan.tool_class or "A",
                confidence=confidence,
                decision_state=policy_decision.decision_state,
                detected=True,
            )
            if not changed:
                if args.verbose:
                    print(f"  {scanner.tool_name}: state unchanged — skipping")
                continue
            if args.verbose and reasons:
                print(f"  {scanner.tool_name}: change detected — {', '.join(reasons)}")

        if args.verbose:
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

        if args.verbose:
            print(f"  Emitting detection.observed event...")
        if emitter.emit(detection_event):
            total_events += 1
            if state_differ is not None:
                state_differ.update(
                    tool_name=scan.tool_name,
                    tool_class=scan.tool_class or "A",
                    confidence=confidence,
                    decision_state=policy_decision.decision_state,
                    detected=True,
                )

        if args.verbose:
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

        if args.verbose:
            print(f"  Emitting policy.evaluated event...")
        if emitter.emit(policy_event):
            total_events += 1

    # Emit detection.cleared for tools that vanished since last cycle
    if state_differ is not None:
        for tool_name in state_differ.cleared_tools(detected_tools):
            if args.verbose:
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
                total_events += 1
            state_differ.mark_cleared(tool_name)

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
    emitter: HttpEmitter,
    hostname: str,
    interval: int,
    stop_event: threading.Event,
) -> None:
    """Background thread: send heartbeats every interval seconds."""
    while not stop_event.wait(timeout=interval):
        emitter.heartbeat(hostname=hostname, interval_seconds=interval)


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


def _run_daemon(args: argparse.Namespace) -> None:
    """Run the collector as a persistent daemon until SIGINT/SIGTERM."""
    hostname = args.endpoint_id
    emitter = HttpEmitter(api_url=args.api_url, api_key=args.api_key)
    differ = StateDiffer(report_all=args.report_all)

    stop_event = threading.Event()

    def _handle_signal(signum: int, frame: Any) -> None:
        print(f"\nReceived signal {signum}, shutting down daemon…", file=sys.stderr)
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop,
        args=(emitter, hostname, args.interval, stop_event),
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

        run_scan(args, emitter=emitter, state_differ=differ)

        if stop_event.wait(timeout=args.interval):
            break

    # Emit graceful shutdown event so the API can distinguish between
    # a clean stop (decommission/restart) and a killed process (tamper).
    shutdown_event = _build_lifecycle_event(
        event_type="agent.shutdown",
        endpoint_id=hostname,
        actor_id=args.actor_id,
        summary="Collector agent shutting down gracefully",
    )
    emitter.emit(shutdown_event)

    stop_event.set()
    print("Agentic-gov endpoint agent stopped.", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Endpoint telemetry collector for agentic AI tool detection",
    )
    parser.add_argument(
        "--output", default="./scan-results.ndjson",
        help="Output file for NDJSON events (default: ./scan-results.ndjson)",
    )
    parser.add_argument(
        "--endpoint-id", default=socket.gethostname(),
        help="Endpoint identifier (default: hostname)",
    )
    parser.add_argument(
        "--actor-id", default=getpass.getuser(),
        help="Actor/user identifier (default: current OS user)",
    )
    parser.add_argument(
        "--sensitivity", default="Tier0",
        choices=["Tier0", "Tier1", "Tier2", "Tier3"],
        help="Asset sensitivity tier (default: Tier0)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print events to stdout instead of writing to file",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed scan progress",
    )
    # Daemon / agent mode flags
    parser.add_argument(
        "--interval", type=int, default=0, metavar="SECONDS",
        help="Run as persistent daemon, scanning every N seconds (0 = one-shot)",
    )
    parser.add_argument(
        "--api-url", default=None, metavar="URL",
        help="Central API base URL, e.g. http://localhost:8000",
    )
    parser.add_argument(
        "--api-key", default=None, metavar="KEY",
        help="API key for authenticating with the central server",
    )
    parser.add_argument(
        "--report-all", action="store_true",
        help="Report all detections every cycle (default: changes only)",
    )
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
