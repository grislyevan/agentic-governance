#!/usr/bin/env python3
"""Measure CPU and memory footprint of the Detec endpoint agent during scan cycles.

Runs 3 dry-run scan cycles in-process and samples RSS (resident set size) and
CPU usage. Outputs mean/max RSS in MB and CPU% for documentation and
release validation. See docs/endpoint-footprint.md.

Usage (from repo root):
  python scripts/measure_endpoint_footprint.py
  python scripts/measure_endpoint_footprint.py --cycles 5
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COLLECTOR_DIR = str(REPO_ROOT / "collector")
if COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, COLLECTOR_DIR)

import psutil


def _sample_self() -> tuple[float, float]:
    """Return (rss_mb, cpu_percent) for current process."""
    proc = psutil.Process(os.getpid())
    rss_mb = proc.memory_info().rss / (1024 * 1024)
    cpu = proc.cpu_percent(interval=None)
    return (rss_mb, cpu)


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure endpoint agent CPU and memory footprint.")
    parser.add_argument("--cycles", type=int, default=3, help="Number of scan cycles to run (default 3)")
    parser.add_argument("--output", type=str, default=None, help="Write results to this path (default stdout only)")
    args = parser.parse_args()

    from main import run_scan

    run_args = argparse.Namespace(
        endpoint_id="footprint-measure",
        actor_id="footprint-measure",
        sensitivity="medium",
        dry_run=True,
        verbose=False,
        output=str(REPO_ROOT / "scripts" / "footprint-out.jsonl"),
        _on_alert=None,
        telemetry_provider="polling",
        enforcement_posture="passive",
        auto_enforce_threshold=0.75,
        network_allowlist_path=None,
    )
    out_path = Path(run_args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rss_samples: list[float] = []
    cpu_samples: list[float] = []

    rss_mb, cpu = _sample_self()
    rss_samples.append(rss_mb)
    cpu_samples.append(cpu)

    for i in range(args.cycles):
        run_scan(run_args)
        rss_mb, cpu = _sample_self()
        rss_samples.append(rss_mb)
        cpu_samples.append(cpu)
        if i < args.cycles - 1:
            time.sleep(0.5)

    rss_mean = sum(rss_samples) / len(rss_samples)
    rss_max = max(rss_samples)
    cpu_mean = sum(cpu_samples) / len(cpu_samples) if cpu_samples else 0.0
    cpu_max = max(cpu_samples) if cpu_samples else 0.0

    lines = [
        "Endpoint agent footprint (dry-run, polling provider)",
        f"  Cycles: {args.cycles}",
        f"  RSS: mean={rss_mean:.2f} MB  max={rss_max:.2f} MB",
        f"  CPU: mean={cpu_mean:.1f}%  max={cpu_max:.1f}%",
    ]
    text = "\n".join(lines) + "\n"
    print(text)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
