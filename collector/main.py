"""CLI entrypoint: runs scans, scores confidence, evaluates policy, emits events."""

from __future__ import annotations

import argparse
import getpass
import logging
import platform
import socket
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from engine.confidence import classify_confidence, compute_confidence
from engine.policy import PolicyDecision, evaluate_policy
from output.emitter import EventEmitter
from scanner.base import ScanResult
from scanner.claude_code import ClaudeCodeScanner
from scanner.copilot import CopilotScanner
from scanner.cursor import CursorScanner
from scanner.ollama import OllamaScanner
from scanner.open_interpreter import OpenInterpreterScanner

EVENT_VERSION = "0.1.0"


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


def run_scan(args: argparse.Namespace) -> int:
    """Execute the full scan pipeline."""
    session_id = str(uuid.uuid4())
    trace_id = f"trace-collector-{session_id[:8]}"
    endpoint_id = args.endpoint_id
    actor_id = args.actor_id
    sensitivity = args.sensitivity

    if args.verbose:
        print(f"Collector session: {session_id}")
        print(f"Endpoint: {endpoint_id}  Actor: {actor_id}  Sensitivity: {sensitivity}")
        print("-" * 60)

    emitter = EventEmitter(
        output_path=args.output,
        dry_run=args.dry_run,
    )

    scanners = [
        ClaudeCodeScanner(),
        OllamaScanner(),
        CursorScanner(),
        CopilotScanner(),
        OpenInterpreterScanner(),
    ]
    total_events = 0

    for scanner in scanners:
        if args.verbose:
            print(f"\n--- Scanning for {scanner.tool_name} ---")

        scan = scanner.scan(verbose=args.verbose)

        if not scan.detected:
            if args.verbose:
                print(f"  {scanner.tool_name}: Not detected")
            continue

        confidence = compute_confidence(scan)
        conf_class = classify_confidence(confidence)

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

        policy_decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=scan.tool_class or "A",
            sensitivity=sensitivity,
            action_risk=scan.action_risk,
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

    stats = emitter.stats
    if args.verbose:
        print(f"\n{'=' * 60}")
    print(f"Scan complete. Events emitted: {stats['emitted']}, "
          f"validation failures: {stats['failed']}")
    if not args.dry_run:
        print(f"Output: {args.output}")

    return 0 if stats["failed"] == 0 else 1


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
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    sys.exit(run_scan(args))


if __name__ == "__main__":
    main()
