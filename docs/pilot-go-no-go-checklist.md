# Pilot Go / No-Go Checklist

Use this checklist before advancing from one pilot rollout stage to the next. All go criteria must be checked. Any no-go blocker requires a stop. Document the decision and who authorized it before proceeding.

---

## Go Criteria

All items must be met before advancing the pilot stage.

| # | Criterion | Checked |
|---|-----------|---------|
| 1 | Events are flowing from **all** endpoints in the current stage (last-seen timestamp within 2× scan interval for every registered endpoint) | ☐ |
| 2 | No hard-stop triggers are currently active (see [pilot-runbook.md](pilot-runbook.md) hard-stop table) | ☐ |
| 3 | Baseline false-positive rate is acceptable (target: <5% of sessions in the 48-hour window are confirmed FP) | ☐ |
| 4 | At least one analyst has triaged sessions in the dashboard without requiring engineering support | ☐ |
| 5 | Every enforcement decision in the current stage has an audit trail entry in the dashboard Audit Log | ☐ |
| 6 | Rollback path has been verified: agent can be stopped and unregistered, and server retains no blocking rules for the endpoint after uninstall | ☐ |
| 7 | Residual risks for the current stage have been documented (open FP scenarios, tools with known detection gaps, OS-specific enforcement caveats) | ☐ |
| 8 | Policy rules in use have been reviewed and intentional escalations (Warn / Approval Required) are confirmed as deliberate | ☐ |
| 9 | Confidence scores for detected tools are consistent with published baseline ranges (no unexplained drops >20 percentage points vs prior stage) | ☐ |
| 10 | Customer contact / pilot sponsor has been briefed on current stage findings and has approved proceeding | ☐ |

---

## No-Go Criteria / Blockers

Any one of the following blocks advancement until resolved.

| # | Blocker | Status |
|---|---------|--------|
| 1 | Zero events on any registered endpoint after confirming the agent is running (>10 minutes with no event ingest) | Blocking |
| 2 | Enforcement action (process kill or network null-route) was applied to a process confirmed not to be an AI tool | Blocking |
| 3 | API server was unreachable from endpoints for >30 minutes during the stage window | Blocking |
| 4 | Confidence score dropped >20 percentage points on a previously stable detection without a known cause (scanner change, fixture update, or environment change) | Blocking |
| 5 | Unknown schema errors or parse failures are appearing in server ingest logs (schema version mismatch between agent and server) | Blocking |
| 6 | Rollback procedure has not been tested and verified for the current OS type in use | Blocking |

---

## Escalation Path

**Who decides go/no-go:** The pilot operator or designated analyst is responsible for completing this checklist. If any no-go blocker is present, escalate to the engineering contact before proceeding.

**How to document:**
1. Complete this checklist and save a copy with the stage number and date in the pilot record (e.g., `pilot-stage-1-go-nogo-2026-03-24.md`).
2. Record the decision (Go / No-Go), who authorized it, and any open residual risks that were accepted.
3. File the record alongside the pilot evidence artifacts for audit trail purposes.

If a no-go decision is made, document the blocker, the remediation steps taken, and re-run the checklist after remediation before re-attempting the stage gate.
