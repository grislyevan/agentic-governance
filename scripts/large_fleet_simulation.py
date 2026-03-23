#!/usr/bin/env python3
"""Simulate a large fleet of agents: heartbeats and event ingest.

Sends many heartbeats and events to the API to measure throughput and
behavior under load. Requires a running API and auth (API key or login).
See docs/large-fleet-scenario.md.

Usage (from repo root):
  export API_URL=http://localhost:8000
  export API_KEY=your-key   # or SEED_ADMIN_EMAIL + SEED_ADMIN_PASSWORD for login
  python scripts/large_fleet_simulation.py --agents 50
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import httpx
except ImportError:
    print("pip install httpx", file=sys.stderr)
    sys.exit(1)


API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")
API_PREFIX = "/api"


def get_auth_headers() -> dict[str, str]:
    api_key = os.environ.get("API_KEY")
    if api_key:
        return {"X-API-Key": api_key}
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@example.com")
    password = os.environ.get("SEED_ADMIN_PASSWORD", "change-me")
    with httpx.Client() as client:
        r = client.post(
            f"{API_URL}{API_PREFIX}/auth/login",
            data={"username": email, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.status_code != 200:
            raise SystemExit(f"Login failed: {r.status_code} {r.text}")
        token = r.json().get("access_token")
        if not token:
            raise SystemExit("No access_token in login response")
        return {"Authorization": f"Bearer {token}"}


def run(
    agents: int = 50,
    events_per_agent: int = 1,
    timeout: float = 30.0,
) -> None:
    headers = get_auth_headers()

    # Heartbeats
    heartbeat_t0 = time.perf_counter()
    heartbeat_ok = 0
    heartbeat_429 = 0
    with httpx.Client(timeout=timeout) as client:
        for i in range(agents):
            r = client.post(
                f"{API_URL}{API_PREFIX}/endpoints/heartbeat",
                json={"hostname": f"fleet-{i:05d}", "interval_seconds": 300},
                headers=headers,
            )
            if r.status_code == 200:
                heartbeat_ok += 1
            elif r.status_code == 429:
                heartbeat_429 += 1
    heartbeat_elapsed = time.perf_counter() - heartbeat_t0

    # Events (minimal payload)
    event_t0 = time.perf_counter()
    event_ok = 0
    event_429 = 0
    total_events = agents * events_per_agent
    with httpx.Client(timeout=timeout) as client:
        for i in range(total_events):
            body = {
                "event_id": str(uuid.uuid4()),
                "event_type": "detection",
                "event_version": "1.0",
                "observed_at": "2026-03-01T12:00:00Z",
                "tool": {"name": "Ollama", "class": "B"},
                "policy": {"decision_state": "detect"},
                "severity": {"level": "P3"},
                "endpoint": {"id": f"fleet-{i % agents:05d}", "hostname": f"fleet-{i % agents:05d}", "os": "Linux"},
            }
            r = client.post(f"{API_URL}{API_PREFIX}/events", json=body, headers=headers)
            if r.status_code in (200, 201):
                event_ok += 1
            elif r.status_code == 429:
                event_429 += 1
    event_elapsed = time.perf_counter() - event_t0

    print("Large-fleet simulation results")
    print(f"  API: {API_URL}")
    print(f"  Agents (heartbeats): {agents}")
    print(f"  Heartbeats: {heartbeat_ok} ok, {heartbeat_429} rate-limited, {heartbeat_elapsed:.2f}s")
    if heartbeat_elapsed > 0:
        print(f"  Heartbeat throughput: {heartbeat_ok / heartbeat_elapsed:.1f}/s")
    print(f"  Events: {total_events} total, {event_ok} ok, {event_429} rate-limited, {event_elapsed:.2f}s")
    if event_elapsed > 0:
        print(f"  Event throughput: {event_ok / event_elapsed:.1f}/s")
    if heartbeat_429 or event_429:
        print("  Note: rate limits (60/min heartbeat, 120/min events per IP) may cap throughput from one client.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate many agents (heartbeat + events).")
    parser.add_argument("--agents", type=int, default=50, help="Number of distinct agents (heartbeats)")
    parser.add_argument("--events-per-agent", type=int, default=1, help="Events to send per agent")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout per request")
    args = parser.parse_args()
    run(agents=args.agents, events_per_agent=args.events_per_agent, timeout=args.timeout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
