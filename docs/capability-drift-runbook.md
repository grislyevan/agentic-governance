# Capability Drift Runbook

## What is capability drift?

Capability drift occurs when an AI agent's detected capabilities change unexpectedly relative to its baseline profile. Examples:
- An agent previously seen making only read operations starts making write or network requests
- An agent's tool usage pattern shifts outside the expected confidence envelope
- A new tool class appears in session reports that was not previously observed

## Severity levels

| Severity | Drift count per endpoint | Action |
|---|---|---|
| Low | 1 | Monitor; review at next weekly cadence |
| Medium | 2 | Investigate within 24 hours; check session reports |
| High | 3+ | Immediate review; consider temporary suspension |

## Detection signals

Drift is detected from `session_reports.evasion_vectors` when the vector `"capability_drift"` appears. The `CapabilityDriftWidget` on the dashboard aggregates these by endpoint.

A Prometheus counter `detec_agent_capability_drift_total` increments server-side for every drift event ingested.

## Investigation steps

### 1. Identify affected endpoints

Check the Capability Drift widget on the dashboard. Click an endpoint row to view its session reports.

### 2. Review session reports

Navigate to **Events → Session Reports** and filter by the affected endpoint. Look for:
- When drift was first detected (earliest `created_at` with `capability_drift`)
- Which tool class triggered the drift (inspect `tool_class` in the event)
- Whether the agent was recently updated or redeployed

### 3. Cross-reference with allow-list

Check `/enforcement/allow-list` for entries covering the drifting agent. If the agent is allow-listed, the drift may still be captured but enforcement is suppressed.

### 4. Decision matrix

| Situation | Recommended action |
|---|---|
| Agent was updated legitimately | Update baseline in allow-list; add reason_code `version_update` |
| Unexplained new capabilities | Set policy to `approval_required` for this endpoint; open security review |
| Repeated evasion pattern | Escalate to security team; consider `block` policy |
| False positive (known safe pattern) | Add to allow-list with `known_safe` reason_code and expiry |

### 5. Document your decision

Record your finding in the weekly FP/FN review log (see `docs/detection-review-cadence.md`).

## Metrics to watch

- `detec_agent_capability_drift_total` — cumulative drift events (Prometheus)
- Dashboard Capability Drift widget — per-endpoint severity

## Escalation

If drift is observed on more than 3 endpoints simultaneously, or if drift coincides with a known threat campaign, escalate to the security team immediately.
