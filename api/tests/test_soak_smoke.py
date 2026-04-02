"""Soak smoke test — 10-iteration in-process replay of the soak harness logic.

This is the in-process equivalent of running:
    scripts/soak/replay_traces.py --iterations 10 --interval-seconds 0

It uses the TestClient + conftest in-memory DB so it runs without a staging
server. Validates:
  1. Benign events ingest successfully (200/201)
  2. Agentic (BEH-008) events ingest successfully
  3. BEH-008 traces are present in the event log after ingest
  4. No 500 errors across all iterations
  5. events_ingested metric increases by 2 × iterations
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import API, _auth_header, register_user

ITERATIONS = 10


def _benign_event(i: int, endpoint_id: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": {"id": endpoint_id},
        "tool": {"name": "vscode", "class": "A", "attribution_confidence": 0.25},
        "policy": {"decision_state": "allow", "rule_id": "DEFAULT-ALLOW"},
        "severity": {"level": "info"},
    }


def _agentic_beh008_event(i: int, endpoint_id: str) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "event_type": "detection.observed",
        "event_version": "1.0",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": {"id": endpoint_id},
        "tool": {"name": "unknown-agent", "class": "D", "attribution_confidence": 0.85},
        "policy": {"decision_state": "block", "rule_id": "BEH-008"},
        "severity": {"level": "critical"},
        "evidence_details": {
            "behavioral_patterns": [
                {
                    "pattern_id": "BEH-008",
                    "evidence": {"resurrection_count": 3},
                }
            ]
        },
    }


class TestSoakSmoke:
    """10-iteration smoke equivalent of the 24h soak harness."""

    def test_replay_10_iterations(self, client):
        headers = _auth_header(
            register_user(client, "soak-smoke@test.com", tenant_name="SoakSmoke")[
                "access_token"
            ]
        )
        endpoint_id = f"soak-host-{uuid.uuid4().hex[:8]}"
        failed = 0
        sent = 0

        for i in range(ITERATIONS):
            # Benign
            r = client.post(
                f"{API}/events", json=_benign_event(i, endpoint_id), headers=headers
            )
            sent += 1
            if r.status_code not in (200, 201):
                failed += 1

        # Agentic BEH-008
        r = client.post(
            f"{API}/events",
            json=_agentic_beh008_event(i, endpoint_id),
            headers=headers,
        )
        sent += 1
        if r.status_code not in (200, 201):
            failed += 1

        assert failed == 0, (
            f"{failed}/{sent} event ingest requests failed. "
            f"Last response: {r.status_code} {r.text[:300]}"
        )

    def test_beh008_present_after_ingest(self, client):
        """BEH-008 events are queryable after ingest."""
        headers = _auth_header(
            register_user(client, "soak-beh008@test.com", tenant_name="SoakBEH008")[
                "access_token"
            ]
        )
        endpoint_id = f"beh008-host-{uuid.uuid4().hex[:8]}"

        ev = _agentic_beh008_event(0, endpoint_id)
        ev_id = ev["event_id"]
        r = client.post(f"{API}/events", json=ev, headers=headers)
        assert r.status_code in (200, 201), r.text

        # Query back
        q = client.get(f"{API}/events", headers=headers)
        assert q.status_code == 200
        items = q.json().get("items", [])
        ids = [e["event_id"] for e in items]
        assert ev_id in ids

    def test_no_500s_across_iterations(self, client):
        """Repeated ingest never returns 5xx."""
        headers = _auth_header(
            register_user(client, "soak-no500@test.com", tenant_name="SoakNo500")[
                "access_token"
            ]
        )
        endpoint_id = f"no500-host-{uuid.uuid4().hex[:8]}"
        errors = []

        for i in range(ITERATIONS):
            for ev in [
                _benign_event(i, endpoint_id),
                _agentic_beh008_event(i, endpoint_id),
            ]:
                r = client.post(f"{API}/events", json=ev, headers=headers)
                if r.status_code >= 500:
                    errors.append((r.status_code, r.text[:100]))

        assert errors == [], f"Got 5xx responses: {errors}"

    def test_event_count_increases(self, client):
        """Event list total grows by exactly 2 × iterations."""
        headers = _auth_header(
            register_user(client, "soak-count@test.com", tenant_name="SoakCount")[
                "access_token"
            ]
        )
        endpoint_id = f"count-host-{uuid.uuid4().hex[:8]}"

        before = client.get(f"{API}/events", headers=headers).json().get("total", 0)

        for i in range(ITERATIONS):
            client.post(
                f"{API}/events", json=_benign_event(i, endpoint_id), headers=headers
            )
            client.post(
                f"{API}/events",
                json=_agentic_beh008_event(i, endpoint_id),
                headers=headers,
            )

        after = client.get(f"{API}/events", headers=headers).json().get("total", 0)
        assert after == before + (ITERATIONS * 2), (
            f"Expected {before + ITERATIONS * 2} events, got {after}"
        )
