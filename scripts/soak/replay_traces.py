#!/usr/bin/env python3
"""Replay synthetic benign + agentic traces and capture /metrics deltas.

This script is intended for 24-72h soak windows; it can also run short smoke loops.
It posts canonical events to /events and snapshots selected Prometheus counters from /metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_METRICS = [
    "detec_events_ingested_total",
    "detec_playbook_runs_total",
    "detec_playbook_run_outcomes_total",
    "detec_gateway_decode_errors_total",
    "detec_gateway_handler_errors_total",
    "detec_gateway_db_errors_total",
    "detec_gateway_transport_errors_total",
    "detec_gateway_webhook_errors_total",
    "detec_enforcement_actions_total",
    "detec_beh009_hits_total",
]


@dataclass
class ReplayResult:
    sent: int = 0
    success: int = 0
    failed: int = 0


def _http_json(url: str, method: str = "GET", payload: dict[str, Any] | None = None, api_key: str | None = None) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key

    req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")
        if not body:
            return None
        return json.loads(body)


def _http_text(url: str, api_key: str | None = None) -> str:
    headers = {"Accept": "text/plain"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url=url, method="GET", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_metrics(text: str, metric_names: list[str]) -> dict[str, float]:
    out: dict[str, float] = {}
    wanted = tuple(metric_names)
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not line.startswith(wanted):
            continue
        # Prom metric line shape: name{labels} value  OR  name value
        try:
            parts = line.rsplit(" ", 1)
            if len(parts) != 2:
                continue
            name, value = parts
            out[name] = float(value)
        except ValueError:
            continue
    return out


def _base_event(endpoint_id: str, hostname: str, session_id: str, trace_id: str) -> dict[str, Any]:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "trace_id": trace_id,
        "endpoint": {
            "id": endpoint_id,
            "hostname": hostname,
            "os": "macOS synthetic",
            "management_state": "managed",
        },
        "actor": {"type": "user", "id": "soak-harness"},
        "posture": {"mode": "active"},
        "severity": {"level": "medium"},
    }


def benign_event(endpoint_id: str, hostname: str, iteration: int) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    trace_id = f"benign-{iteration}-{uuid.uuid4().hex[:8]}"
    evt = _base_event(endpoint_id, hostname, session_id, trace_id)
    evt.update(
        {
            "tool": {
                "name": "VSCode",
                "class": "A",
                "version": "1.0",
                "attribution_confidence": 0.42,
            },
            "action": {"type": "file_read", "verb": "read"},
            "target": {"kind": "file", "path": "/tmp/README.md"},
            "policy": {
                "decision_state": "detect",
                "rule_id": "SOAK-BENIGN-DETECT",
            },
            "outcome": {"status": "allowed"},
            "evidence_details": {
                "behavioral_patterns": [
                    {
                        "pattern_id": "BEH-001",
                        "name": "Shell fan-out",
                        "score": 0.25,
                    }
                ]
            },
        }
    )
    return evt


def agentic_event(endpoint_id: str, hostname: str, iteration: int, ttl_seconds: int) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    trace_id = f"agentic-{iteration}-{uuid.uuid4().hex[:8]}"
    evt = _base_event(endpoint_id, hostname, session_id, trace_id)
    evt.update(
        {
            "tool": {
                "name": "Unknown Agent",
                "class": "D",
                "version": "0",
                "attribution_confidence": 0.93,
            },
            "action": {"type": "process_resurrection", "verb": "restart"},
            "target": {"kind": "process", "name": "node"},
            "policy": {
                "decision_state": "block",
                "rule_id": "BEH-008-RESURRECTION",
            },
            "enforcement": {
                "action": "network_null_route",
                "detail": f"synthetic block with TTL auto-unblock in {ttl_seconds}s",
                "process_name": "node",
                "pid": 4242,
                "pids_killed": [4242, 4243],
            },
            "outcome": {"status": "blocked"},
            "severity": {"level": "high"},
            "evidence_details": {
                "behavioral_patterns": [
                    {
                        "pattern_id": "BEH-008",
                        "name": "Process resurrection",
                        "score": 0.98,
                        "evidence": {
                            "restart_count": 3,
                            "window_seconds": 10,
                        },
                    }
                ]
            },
        }
    )
    return evt


def replay(args: argparse.Namespace) -> int:
    base = args.base_url.rstrip("/")
    events_url = urllib.parse.urljoin(base + "/", "events")
    # /metrics is exposed at API host root (not router-prefixed)
    root = base[:-4] if base.endswith("/api") else base
    metrics_url = urllib.parse.urljoin(root.rstrip("/") + "/", "metrics")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    events_out = out_dir / "events-results.jsonl"
    metrics_before_out = out_dir / "metrics-before.json"
    metrics_after_out = out_dir / "metrics-after.json"
    metrics_delta_out = out_dir / "metrics-delta.json"

    # baseline metrics
    metrics_before_text = _http_text(metrics_url, api_key=args.api_key)
    metrics_before = _parse_metrics(metrics_before_text, args.metrics)
    metrics_before_out.write_text(json.dumps(metrics_before, indent=2, sort_keys=True) + "\n")

    result = ReplayResult()
    with events_out.open("w", encoding="utf-8") as f:
        for i in range(args.iterations):
            payloads = [
                benign_event(args.endpoint_id, args.hostname, i),
                agentic_event(args.endpoint_id, args.hostname, i, args.ttl_seconds),
            ]
            for payload in payloads:
                result.sent += 1
                row = {
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                    "event_id": payload["event_id"],
                    "trace_id": payload.get("trace_id"),
                    "kind": "agentic" if payload.get("tool", {}).get("name") == "Unknown Agent" else "benign",
                }
                try:
                    resp = _http_json(events_url, method="POST", payload=payload, api_key=args.api_key)
                    result.success += 1
                    row["ok"] = True
                    row["response_id"] = (resp or {}).get("id")
                except urllib.error.HTTPError as e:
                    result.failed += 1
                    row["ok"] = False
                    row["status"] = e.code
                    row["error"] = e.read().decode("utf-8", errors="replace")
                except Exception as e:  # noqa: BLE001
                    result.failed += 1
                    row["ok"] = False
                    row["error"] = str(e)
                f.write(json.dumps(row) + "\n")
                f.flush()

            if i < args.iterations - 1 and args.interval_seconds > 0:
                time.sleep(args.interval_seconds)

    metrics_after_text = _http_text(metrics_url, api_key=args.api_key)
    metrics_after = _parse_metrics(metrics_after_text, args.metrics)
    metrics_after_out.write_text(json.dumps(metrics_after, indent=2, sort_keys=True) + "\n")

    keys = sorted(set(metrics_before) | set(metrics_after))
    delta = {
        k: {
            "before": metrics_before.get(k, 0.0),
            "after": metrics_after.get(k, 0.0),
            "delta": metrics_after.get(k, 0.0) - metrics_before.get(k, 0.0),
        }
        for k in keys
    }
    metrics_delta_out.write_text(json.dumps(delta, indent=2, sort_keys=True) + "\n")

    summary = {
        "sent": result.sent,
        "success": result.success,
        "failed": result.failed,
        "output_dir": str(out_dir.resolve()),
        "events_url": events_url,
        "metrics_url": metrics_url,
    }
    print(json.dumps(summary, indent=2))
    return 0 if result.failed == 0 else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base-url", default="http://127.0.0.1:8000/api", help="API base URL (default: http://127.0.0.1:8000/api)")
    p.add_argument("--api-key", default=None, help="Tenant agent key or user API key (sent as X-API-Key)")
    p.add_argument("--iterations", type=int, default=12, help="Number of benign+agentic pairs to send")
    p.add_argument("--interval-seconds", type=int, default=60, help="Sleep between iterations")
    p.add_argument("--ttl-seconds", type=int, default=300, help="TTL used in synthetic enforcement detail text")
    p.add_argument("--endpoint-id", default="soak-endpoint-01", help="Synthetic endpoint ID/hostname")
    p.add_argument("--hostname", default="soak-endpoint-01", help="Synthetic hostname")
    p.add_argument("--out-dir", default="scripts/soak/output/latest", help="Output directory")
    p.add_argument(
        "--metrics",
        nargs="+",
        default=DEFAULT_METRICS,
        help="Metric names to snapshot from /metrics (prefix match includes labeled series)",
    )
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.iterations <= 0:
        print("--iterations must be > 0", file=sys.stderr)
        return 2
    return replay(args)


if __name__ == "__main__":
    raise SystemExit(main())
