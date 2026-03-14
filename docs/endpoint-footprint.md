# Endpoint Agent Footprint (CPU, Memory, Scan Latency)

**Workstream 7.** Measured impact of the Detec endpoint agent on the host: CPU, memory, and scan latency. Use this for capacity planning and SOC expectations.

## Scan latency

- **Definition:** Wall-clock time for one full `run_scan()` cycle: start telemetry provider, run all scanners, score and evaluate policy, emit events (or dry-run).
- **Measurement:** Run the collector with `--dry-run --verbose` and measure elapsed time; or use the benchmark in `collector/tests/test_scan_latency_benchmark.py` (see below).
- **Target:** Document baseline (e.g. "typical macOS ARM64: X–Y seconds per scan"). No hard SLA in this doc; product may set one later.
- **Factors:** Number of scanners, telemetry provider (polling vs native), system load, number of running processes.

## CPU and memory

- **Definition:** Process CPU usage and resident set size (RSS) of the agent process during steady-state (e.g. 2–3 scan cycles at default interval) or during a single run.
- **Measurement:** Use `ps` or `psutil` to sample the agent process before/after a short run, or during a daemon loop. Example: run agent in background, sample `ps -o pid,%cpu,rss -p <pid>` every 5s for 30s, report mean/max.
- **Target:** Document baseline (e.g. "idle: X% CPU, Y MB RSS; during scan: Z% CPU"). Repeatable script preferred (e.g. in `collector/tests/` or `scripts/`).
- **Script:** A small script can be added (e.g. `scripts/measure-footprint.sh`) that starts the agent, samples, and prints summary; run manually or in release validation.

## Benchmarks in tree

- **EventStore:** [collector/tests/test_latency_benchmarks.py](../collector/tests/test_latency_benchmarks.py) — push/get latency and throughput for the in-memory store.
- **Scan latency:** [collector/tests/test_scan_latency_benchmark.py](../collector/tests/test_scan_latency_benchmark.py) — times a single `run_scan()` (dry-run) and asserts under a ceiling (e.g. 60s) so regressions are caught.
- **Provider integration:** `test_alert_triggered_scan_latency` in provider integration tests.

## Reporting

- Add a short "Endpoint footprint" subsection to [docs/SECURITY-TECHNICAL-REPORT.md](SECURITY-TECHNICAL-REPORT.md) or keep this doc as the canonical place. INIT-32 benchmark report generator can consume these numbers when implemented.
