# Pilot Runbook

## Overview

A Detec pilot runs in three stages: 5 endpoints → 10 endpoints → 25 endpoints. Each stage gates on the previous stage completing without hard-stop triggers and with events flowing continuously.

The pilot begins in **visibility-only** mode (Detect outcomes only — no enforcement). Analysts review detections, measure false-positive rates, and tune policy before escalating to Warn, then Approval Required. Enforcement (Block) is not enabled during a standard pilot unless the customer explicitly requests it and residual risks are documented.

Go/no-go criteria for advancing between stages are in [docs/pilot-go-no-go-checklist.md](pilot-go-no-go-checklist.md).

---

## Prerequisites

Before deploying:

- Detec server is running and accessible from endpoint machines (HTTP/HTTPS, port 8000; binary gateway port 8001 if used).
- An API key with `admin` or `owner` role is provisioned. Generate via server admin or `POST /api/keys`.
- Endpoint machines are reachable by the operator and have Python 3.11+ installed.
- macOS endpoints: Full Disk Access granted to the Python process or installed agent binary.
- Windows endpoints: Scheduled task template available; user account with access to process list.
- Linux endpoints: systemd service template available; `psutil` readable without elevated permissions for target user.

---

## Deployment Steps

Repeat for each endpoint in the stage batch:

1. **Install the agent.** On the endpoint, run the installer appropriate for the OS:
   - macOS: install `.pkg` via MDM or run the installer directly. Alternatively, install from source: `pip install detec-collector`.
   - Windows: deploy via scheduled task template in `deploy/windows/`. Run `install-agent.ps1` as the target user.
   - Linux: deploy via systemd unit in `deploy/linux/`. Run `install-agent.sh`.

2. **Create the agent config file.** Place `detec-config.json` in the agent config directory (default: `~/.detec/config.json`):

   ```json
   {
     "server_url": "https://<your-server>",
     "api_key": "<your-api-key>",
     "tenant_id": "<tenant-id>",
     "scan_interval_seconds": 30,
     "enforcement_enabled": false
   }
   ```

   Set `enforcement_enabled: false` for visibility-only pilot mode.

3. **Register the endpoint.** On first run, the agent registers itself automatically. Verify registration in the dashboard under **Endpoints** or via:

   ```bash
   curl -H "Authorization: Bearer <api-key>" https://<server>/api/endpoints
   ```

4. **Verify events are flowing.** Within 10 minutes of agent start, confirm events appear in the dashboard under **Sessions** or via:

   ```bash
   curl -H "Authorization: Bearer <api-key>" https://<server>/api/events?limit=10
   ```

   If no events appear after 10 minutes, see the Hard-Stop Triggers table below.

---

## Baseline Capture

After all stage endpoints are registered and events are flowing:

1. Allow at least one full scan cycle to complete (default: 30 seconds per cycle).
2. Open the dashboard → **Sessions** and review detections. Note confidence bands for each tool detected.
3. Export baseline detection output using the CLI:

   ```bash
   detec scan --verbose
   ```

4. Record the baseline: which tools are detected, at what confidence, and with what policy outcome. This is your baseline for measuring false-positive rate.

---

## Policy Tuning

Start in visibility-only mode. Use the 15 baseline rules seeded per tenant as the starting point.

**Step 1 — Review FP rate.** Over 48 hours, identify any detections on processes you know are not AI tools (false positives). Use the dashboard **Sessions** view to triage.

**Step 2 — Adjust threshold overlays.** If a scanner is producing FPs for a specific tool or path, add an overlay rule to raise its threshold or suppress via exception. Overlay rules only escalate, never downgrade.

**Step 3 — Escalate to Warn.** Once FP rate is acceptable (baseline: <5% of sessions in 48 hours should be FP), change relevant rules from `detect` to `warn`. Affected users will see a warning; no blocking occurs.

**Step 4 — Escalate to Approval Required.** For high-risk tools identified in your policy scope, escalate to `approval_required`. Analysts will receive approval requests in the dashboard.

**Step 5 — Document before escalating to Block.** Block is not part of a standard visibility pilot. If escalation to Block is requested, document residual risks, verify rollback path (see [docs/rollback.md](rollback.md)), and ensure enforcement safety matrix review is complete (see [docs/enforcement-safety-matrix.md](enforcement-safety-matrix.md)).

---

## Analyst Workflow

Standard triage path during a pilot:

1. **Dashboard → Endpoints** — confirm all pilot endpoints are reporting and last-seen timestamps are recent.
2. **Dashboard → Sessions** — review sessions with risk signals. Sort by confidence score descending.
3. **Session detail** — for each flagged session, review: tool detected, confidence score, evidence layers that fired, behavioral pattern triggered.
4. **Policy decision** — determine whether the session is a true positive, false positive, or expected behavior. Record notes in the audit log.
5. **Escalate or suppress** — escalate the relevant rule or add a suppression overlay as appropriate.

Session reports are also available via CLI:

```bash
detec scan --verbose
curl -H "Authorization: Bearer <api-key>" https://<server>/api/sessions/<session-id>/report
```

---

## Hard-Stop Triggers

If any of these conditions occur, halt the stage expansion and escalate immediately.

| Trigger | Required Action |
|---------|----------------|
| Zero events on any registered endpoint after confirming agent is running (>10 min) | Stop stage; debug agent connectivity and config; do not advance to next stage |
| Enforcement action (process kill or network block) on a process known not to be an AI tool | Stop enforcement immediately; set `enforcement_enabled: false`; file incident report; investigate rule causing the trigger |
| API server unreachable from endpoints for >30 minutes | Stop stage; restore API connectivity before proceeding; verify server health and TLS config |
| Unexplained confidence drop of >20 percentage points on a previously stable detection | Stop; investigate calibration fixture and scanner logic; do not advance until root cause is identified |
| Unknown schema errors in event ingest (parse failures appearing in server logs) | Stop; check agent version vs server version compatibility; resolve before proceeding |

---

## Rollout Stages

| Stage | Endpoint Count | Gate to Advance |
|-------|---------------|----------------|
| Stage 1 | 5 endpoints | Zero hard-stop triggers in 48 hours AND events flowing from all endpoints |
| Stage 2 | 10 endpoints | Zero hard-stop triggers in 48 hours AND FP rate acceptable AND analyst triage workflow validated |
| Stage 3 | 25 endpoints | Zero hard-stop triggers in 48 hours AND go/no-go checklist signed off |

Complete the [go/no-go checklist](pilot-go-no-go-checklist.md) before advancing from each stage.

---

## Reference Docs

- [docs/pilot-go-no-go-checklist.md](pilot-go-no-go-checklist.md) — go/no-go criteria before expanding a pilot stage
- [docs/product-status.md](product-status.md) — capability maturity and known limitations
- [docs/enforcement-safety-matrix.md](enforcement-safety-matrix.md) — enforcement safety and OS-specific caveats
- [docs/rollback.md](rollback.md) — agent and server rollback procedures
- [SERVER.md](../SERVER.md) — server deployment and first API key setup
- [DEPLOY.md](../DEPLOY.md) — agent auto-start templates (LaunchAgent, systemd, Windows Task)
- [docs/mdm-deployment.md](mdm-deployment.md) — MDM deployment for macOS fleet
- [docs/win-pilot-operator-runbook.md](win-pilot-operator-runbook.md) — Windows-specific pilot operator guide
