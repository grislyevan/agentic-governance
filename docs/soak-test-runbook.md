# Soak Test Runbook (24–72h)

Purpose: run a mixed-behavior soak test that continuously replays synthetic benign and known agentic workflows, validates BEH-008 guard behavior, and verifies TTL auto-unblock resilience across restart/reload.

> Do **not** run the full 72h soak during implementation. This runbook defines how to execute it in staging/pilot.

## Scope

- **In scope**
  - Mixed traces: benign + agentic (includes synthetic BEH-008 process resurrection signal)
  - Metrics collection from `GET /metrics`
  - BEH-008 guard checks (classification + policy path)
  - TTL unblock checks over service restart/reload windows
- **Out of scope**
  - New detector tuning
  - Production rollout decisions

## Preconditions

1. API is reachable (example: `http://127.0.0.1:8000/api`)
2. Valid API key (tenant agent key or user API key) is available
3. Metrics endpoint reachable at `${BASE_URL%/api}/metrics` (or `${BASE_URL}/metrics` if API is mounted there)
4. Test environment permits enforcement simulation/active posture according to your policy

## Workloads to Replay

### Benign workflow (synthetic)

Expected behavior: low/medium risk evidence, non-blocking policy outcomes, no sustained gateway/playbook failures.

- Editor/file-read style event
- `tool.class=A`
- Policy decision: `detect`

### Known agentic workflow (synthetic BEH-008)

Expected behavior: high-confidence unknown/agentic signal, block policy path, enforcement metadata present.

- Unknown agent process resurrection signal
- `pattern_id=BEH-008`
- `tool.class=D`
- Policy decision: `block`
- Enforcement action includes `network_null_route` and TTL-unblock detail text

## Harness Script

Script: `scripts/soak/replay_traces.py` (executable)

What it does:
- Replays benign + agentic event pairs for N iterations
- Captures baseline and final metric snapshots from `/metrics`
- Writes delta report and per-event POST results

### Quick smoke (10–15 min)

```bash
cd /Users/echance/Documents/agentic-governance
export DETEC_BASE_URL="http://127.0.0.1:8000/api"
export DETEC_API_KEY="<api-key>"

scripts/soak/replay_traces.py \
  --base-url "$DETEC_BASE_URL" \
  --api-key "$DETEC_API_KEY" \
  --iterations 10 \
  --interval-seconds 60 \
  --out-dir scripts/soak/output/smoke-$(date +%Y%m%d-%H%M%S)
```

### 24h soak

```bash
cd /Users/echance/Documents/agentic-governance
export DETEC_BASE_URL="http://127.0.0.1:8000/api"
export DETEC_API_KEY="<api-key>"

scripts/soak/replay_traces.py \
  --base-url "$DETEC_BASE_URL" \
  --api-key "$DETEC_API_KEY" \
  --iterations 1440 \
  --interval-seconds 60 \
  --out-dir scripts/soak/output/soak24h-$(date +%Y%m%d-%H%M%S)
```

### 72h soak

```bash
cd /Users/echance/Documents/agentic-governance
export DETEC_BASE_URL="http://127.0.0.1:8000/api"
export DETEC_API_KEY="<api-key>"

scripts/soak/replay_traces.py \
  --base-url "$DETEC_BASE_URL" \
  --api-key "$DETEC_API_KEY" \
  --iterations 4320 \
  --interval-seconds 60 \
  --out-dir scripts/soak/output/soak72h-$(date +%Y%m%d-%H%M%S)
```

## BEH-008 Guard Checks

Run these checks against event data during/after soak:

1. **Signal presence:** agentic traces include `evidence_details.behavioral_patterns[].pattern_id == "BEH-008"`
2. **Classification path:** BEH-008 traces resolve to `tool.class == "D"` (or expected policy tier per current logic)
3. **Decision path:** policy decision is `block` for BEH-008 traces
4. **No cross-impact on benign traces:** benign traces remain mostly `detect/allow` and do not drift into repeated false `block`

Example validation query (adjust URL/auth as needed):

```bash
curl -sS -H "X-API-Key: $DETEC_API_KEY" "$DETEC_BASE_URL/events?page_size=200" > /tmp/soak-events.json
```

Then verify BEH-008 fields in returned `payload` objects.

## TTL Auto-Unblock Checks (Restart/Reload)

Goal: confirm lease/TTL unblock behavior is resilient when services restart/reload during soak.

1. Start soak replay and confirm agentic traces are being ingested
2. Record timestamp `T0`
3. Perform one restart/reload sequence in test env (collector and/or API, per your deployment SOP)
4. Continue replay for at least `2 x TTL` window after restart
5. Validate:
   - No persistent stale block symptoms beyond TTL window
   - Event ingest continues after restart/reload
   - Error metrics do not show sustained escalation

Suggested observation commands:

```bash
export DETEC_METRICS_URL="${DETEC_BASE_URL%/api}/metrics"
curl -sS "$DETEC_METRICS_URL" | grep -E "detec_(events_ingested_total|gateway_.*_errors_total|playbook_run_outcomes_total|enforcement_actions_total)"
```

## Success Criteria

A soak run is considered successful when all conditions hold:

1. Harness completes with `failed = 0` (or documented transient failures within accepted threshold)
2. `detec_events_ingested_total` increases by approximately `2 x iterations`
3. Gateway error counters do not show sustained runaway growth
4. Playbook outcomes remain predominantly successful (`result="success"`)
5. BEH-008 events consistently follow expected guard path (`class D` + `block`)
6. TTL unblock restart/reload check passes (no stale network-block condition beyond TTL window)

## Artifacts Produced by Harness

Each run writes to `--out-dir`:

- `events-results.jsonl` — per-event send result and response/error data
- `metrics-before.json` — selected metric snapshot before replay
- `metrics-after.json` — selected metric snapshot after replay
- `metrics-delta.json` — before/after deltas

## Soak Results Checklist Template

Copy/paste for each soak execution.

```markdown
# Soak Result Record

- Run ID:
- Date/Time (start):
- Date/Time (end):
- Environment:
- Operator:
- Base URL:
- Iterations:
- Interval seconds:
- Output dir:

## Replay Summary
- Sent:
- Success:
- Failed:
- Failure rate (%):

## Metric Checks
- [ ] detec_events_ingested_total increased as expected
- [ ] Gateway error counters stable (no sustained runaway increase)
- [ ] Playbook outcomes mostly success
- [ ] Enforcement action counters align with expected agentic injections

## BEH-008 Guard Checks
- [ ] BEH-008 present in injected agentic traces
- [ ] BEH-008 traces classified as expected (class D / policy tier)
- [ ] BEH-008 traces resolved to block decision
- [ ] Benign traces remained non-blocking (or exceptions documented)

## TTL Unblock Restart/Reload Checks
- Restart/reload performed at:
- TTL configured (s):
- [ ] Ingest resumed after restart/reload
- [ ] No stale block persisted past TTL window
- [ ] No sustained metrics regression post-restart

## Notes / Incidents
-

## Final Verdict
- [ ] PASS
- [ ] PASS WITH RISK ACCEPTANCE
- [ ] FAIL
- Approver(s):
- Follow-up actions:
```

## Run History

| Date       | Duration    | Fatal crashes | Notes |
|------------|-------------|---------------|-------|
| 2026-03-24 | import only | 0             | N1 fix applied (PydanticUndefinedAnnotation resolved, commit d63e3bf). Script invokes correctly (`--help` passes). Full server soak requires Postgres — run with `make dev` in `api/`. Direct invocation via `python3 scripts/soak/replay_traces.py` works; blake2 warnings from pyenv/OpenSSL mismatch are non-fatal. |
