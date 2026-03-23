"""Scan latency benchmark: wall-clock time for one run_scan() cycle.

Marked @pytest.mark.benchmark and @pytest.mark.slow. Establishes baseline for
endpoint footprint (Workstream 7) and regression (e.g. scan must complete
within 60s on typical hardware).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pytest

from main import run_scan


@pytest.mark.benchmark
@pytest.mark.slow
def test_run_scan_dry_run_completes_under_60_seconds(tmp_path) -> None:
    """One full run_scan (dry-run) completes within 60s.

    Uses default args (no API, no enforcer). Telemetry uses polling.
    Target 60s is permissive; tighten for CI or specific hardware.
    """
    args = argparse.Namespace(
        endpoint_id="bench-endpoint",
        actor_id="bench-actor",
        sensitivity="medium",
        dry_run=True,
        verbose=False,
        output=str(tmp_path / "events.jsonl"),
        _on_alert=None,
        telemetry_provider="polling",
        enforcement_posture="passive",
        auto_enforce_threshold=0.75,
        network_allowlist_path=None,
    )
    t0 = time.perf_counter()
    run_scan(args)
    elapsed = time.perf_counter() - t0
    assert elapsed < 60.0, f"run_scan took {elapsed:.1f}s, target < 60s"
