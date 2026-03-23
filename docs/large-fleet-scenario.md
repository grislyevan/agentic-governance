# Large-Fleet Scenario (Many Agents)

**Workstream 4 (Task 4.3).** Simulate many endpoint agents heartbeating and sending events to measure API and gateway behavior under load. Use for capacity planning and documentation of limits.

## Script

- **Script:** [scripts/large_fleet_simulation.py](../scripts/large_fleet_simulation.py) sends heartbeats and events to a running API. Requires auth via `API_KEY` or login (`SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`).
- **Usage:** Start the API (e.g. `cd api && uvicorn main:app`), then from repo root:
  - `export API_URL=http://localhost:8000`
  - `export API_KEY=your-tenant-api-key` (or use default admin login)
  - `python scripts/large_fleet_simulation.py --agents 50`
- **Options:** `--agents N` (default 50), `--events-per-agent N` (default 1), `--timeout T` (seconds).
- **Output:** Heartbeat and event counts (ok vs rate-limited), elapsed time, and throughput (requests/sec). Rate limits (60/min for heartbeat, 120/min for events per IP) will cap throughput when running from a single client; for true fleet scale use many clients or disable rate limits in test.

## Interpretation

- **Single-client limit:** From one IP, heartbeat is limited to 60/minute and events to 120/minute. The script reports how many requests succeeded vs 429 so you can see when limits are hit.
- **Gateway:** For binary protocol (port 8001), connection limits and message throughput are not exercised by this HTTP script; a separate gateway load test would be needed.
- **Baseline:** Run with e.g. 50 agents and record results. Example: "50 heartbeats: 50 ok in 2.1s (24/s); 50 events: 50 ok in 1.8s (28/s). No 429 at 50 agents from one client." Document in this file or in SECURITY-TECHNICAL-REPORT.

## Recommendations

- For production fleet sizing, run the API under expected load (many concurrent heartbeat and event streams) and measure latency and error rate. This script is a simple repeatable baseline from one process.
