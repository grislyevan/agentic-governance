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

---

## Scale Envelope (Architecture Analysis)

The following limits are derived from code analysis and architecture review. Formal load test results against a dedicated staging environment have not yet been collected.

### Rate Limits (as implemented in `api/core/rate_limit.py` and per-route overrides)

| Endpoint | Rate limit | Scope |
|---|---|---|
| `POST /api/endpoints/heartbeat` | 60/min | Per source IP (SlowAPI, `get_remote_address`) |
| `POST /api/events` | 120/min | Per source IP |
| Global default | 300/min | Per source IP |

These limits are enforced by SlowAPI keyed on the remote IP address. All agents sharing a single IP (e.g. all agents in the simulation script running from one host) share the same limit bucket. Rate limiting is disabled when `TESTING=1`.

### Database Tier

| Backend | Suitability | Notes |
|---|---|---|
| SQLite | Evaluation and small pilots only (<50 endpoints) | Not recommended for production; concurrent writes from many agents cause lock contention |
| PostgreSQL | Standard single-server: 100–500 endpoint deployments | Formally tested scale not yet documented; recommended for all production deployments |

### TCP Gateway (port 8001)

- Connection count is limited by OS file descriptor limits (default 256 on macOS, 1024+ on Linux; configurable via `ulimit -n`).
- No explicit connection cap is enforced in gateway code (`gateway/session_registry.py`).
- Tested scenario: 50 concurrent connections from the simulation script. No gateway-side limit was hit.

---

## Bottleneck Matrix

| Component | Known bottleneck | Condition | Mitigation |
|---|---|---|---|
| API rate limiter (SlowAPI, IP-keyed) | Single-IP rate limit caps simulation throughput at 60 heartbeats/min and 120 events/min | All agents originate from the same IP (e.g. single simulation process or NAT) | Use per-agent API keys with multi-IP client distribution in production; or tune rate limits per-route for trusted internal networks |
| SQLite | Not suitable for concurrent writes from many agents | >10 concurrent agents writing events simultaneously | Use PostgreSQL in all production deployments |
| Gateway `SessionRegistry` | Linear scan for broadcast; acceptable at <100 sessions | Large fleet broadcast storms (e.g. simultaneous posture push to all agents) | Not a concern at pilot scale; review for deployments >500 endpoints |
| EventStore ring buffer (per-agent) | Max 10,000 events per agent; at high scan rates near 2 Hz, buffer fills within ~80 min | High-frequency scan mode with slow API ingest | Tune `retention_seconds` and `max_events`; default 60s heartbeat interval is safe for all tested scenarios |
| Event ingest endpoint | Rate limited to 120/min per IP | Burst from many agents sharing a single IP | API keys are per-endpoint; use TCP gateway for high-throughput deployments where burst ingest is needed |

---

## Soak Test Status

Soak test runbook defined in [docs/soak-test-runbook.md](soak-test-runbook.md). Formal soak run not yet executed in a dedicated staging environment. Soak test execution is a Wave 3 validation item.

The runbook defines three execution modes:

| Mode | Iterations | Approximate duration |
|---|---|---|
| Quick smoke | 10 | 10–15 minutes |
| 24h soak | 1,440 | ~24 hours |
| 72h soak | 4,320 | ~72 hours |

Success criteria are documented in the runbook; key signal is `detec_events_ingested_total` increasing by approximately `2 × iterations` with no sustained growth in gateway error counters.

---

## Results (actual run)

No results available. The live simulation run was attempted on 2026-03-24 against a local SQLite-backed API (port 8999) but did not complete: the API server failed to start due to a Pydantic forward-reference resolution error (`Platform` undefined annotation in `api/routers/agent_download.py`) in the Python 3.11.6 environment. This is a local environment dependency issue, not a production code defect.

To record actual results, run in a healthy environment and paste output here using this template:

```
Run date: YYYY-MM-DD
Environment: local SQLite / PostgreSQL, single process / multi-process
Agents: N
Events per agent: N
Results:
  Heartbeats: N ok, N rate-limited, Xs (Y/s)
  Events: N ok, N rate-limited, Xs (Y/s)
  Notes: ...
```
