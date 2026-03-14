"""Performance benchmarks for API and event ingest.

Marked with @pytest.mark.benchmark and @pytest.mark.slow; exclude in default runs
via pytest -m 'not benchmark and not slow'.
Aligns with INIT-30/INIT-32 and docs/validation-expansion-architecture.md.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Import app after path setup so api package is available
import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent.parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _minimal_event_payload() -> dict[str, Any]:
    return {
        "event_type": "detection",
        "tool_name": "Claude Code",
        "tool_class": "C",
        "confidence": 0.85,
        "policy": {"decision_state": "detect", "rule_id": None},
        "endpoint": {"id": "bench-host", "hostname": "bench-host", "os": "Darwin"},
    }


@pytest.mark.benchmark
@pytest.mark.slow
def test_events_ingest_throughput(client: TestClient) -> None:
    """POST /api/events: measure requests per second for event ingest.

    Uses anonymous auth (no API key) so rate limits may apply; goal is to
    establish a baseline for API throughput. Target: document baseline in
    SECURITY-TECHNICAL-REPORT or validation-expansion docs.
    """
    payload = _minimal_event_payload()
    n = 50
    t0 = time.perf_counter()
    for i in range(n):
        payload["endpoint"] = {"id": f"bench-host-{i}", "hostname": f"bench-host-{i}", "os": "Darwin"}
        r = client.post("/api/events", json=payload)
        assert r.status_code in (200, 201, 401, 403), r.text
    elapsed = time.perf_counter() - t0
    rps = n / elapsed
    assert rps > 0
    assert elapsed < 60.0, f"50 requests took {elapsed:.1f}s"
