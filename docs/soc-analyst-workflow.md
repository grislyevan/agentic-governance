# SOC Analyst Workflow

This document covers the standard triage path from detection event to analyst verdict. It is written for users with owner, admin, or analyst roles operating the Detec dashboard and API. No engineering involvement is required for the scenarios described here; escalation criteria for engineering are listed in [Escalation Path](#escalation-path).

---

## Triage Flow Overview

1. **Endpoint scan** — The agent runs on the endpoint and emits detection events containing `tool_name`, `confidence_score`, `confidence_band`, `policy_decision`, action data, and MITRE tactics.
2. **Event ingest** — The API receives and stores each event. Events are stamped with endpoint ID, timestamp, and a unique event ID.
3. **Session grouping** — Events from the same endpoint and tool within a 15-minute gap window are grouped into a session. Session boundaries close when no new event arrives within that window.
4. **Risk signal mapping** — The session aggregator maps action types (`exec`, `write`, `read`, `network`, `repo`, `privileged`, `removal`, `observe`) and MITRE tactics to risk signal labels (e.g., Execution → `execution`, Credential Access → `credential access`, Exfiltration → `exfiltration`).
5. **Dashboard review** — The analyst navigates to the relevant endpoint and session, reviews the risk summary, behavior chain, action counts, and evidence timeline.
6. **Policy decision → verdict** — The analyst evaluates the session against the active policy decision (`detect`, `warn`, `approval_required`, `block`), determines whether it is accurate, and records a verdict. If the policy decision needs adjustment, the analyst edits the policy or adds an allow-list entry.

---

## Step-by-Step Analyst Path

### Scenario 1: Tool detected at Medium confidence, no enforcement

**What triggers it:** A session arrives with `confidence_band: Medium` and `policy_decision: detect`. No enforcement action has fired.

**Dashboard path:** Endpoints → select endpoint → Sessions → filter by endpoint ID → open session detail.

**What to look for:**
- `action_counts`: note counts for `exec`, `write`, `network`.
- `risk_signals`: check whether `execution`, `network access`, or `data staging` labels are present.
- `strongest_subchain`: review the behavior chain for sequencing (e.g., exec followed by write followed by network).
- MITRE tactics in the event timeline.

**Suggested verdict:**
- If `exec` + `write` + `network` are all present, and the tool is an AI tool — escalate: edit the policy rule to `warn` for this tool class and confidence band.
- If only `read` actions are present with no network activity — leave at `detect`. Log a note confirming the review.

---

### Scenario 2: Tool detected at High confidence, approval_required decision

**What triggers it:** A session arrives with `confidence_band: High` and `policy_decision: approval_required`. The session is held pending analyst review.

**Dashboard path:** Endpoints → select endpoint → Sessions → open session detail → review Risk Summary and Evidence tabs.

**What to look for:**
- `risk_signals`: check specifically for `credential access` and `exfiltration` labels.
- `policy_decision` field confirms `approval_required` is active (not a stale cache).
- Audit log: confirm the hold was applied at the correct time and tied to this session.
- `strongest_subchain`: does the behavior chain end with a sensitive action (file write to credential path, outbound connection)?

**Suggested verdict:**
- If no sensitive risk signals (`credential access`, `exfiltration`) are present — downgrade: edit the policy rule to `warn` for this tool and confidence band, then log the change in the audit note.
- If sensitive risk signals are present — uphold the `approval_required` decision. Document the justification in the audit log note before resolving.

---

### Scenario 3: Block decision fired

**What triggers it:** A session arrives with `policy_decision: block`. Enforcement is in `active` posture.

**Dashboard path:** Endpoints → select endpoint → Sessions → open session detail → Events timeline → look for `enforcement.applied` event → Audit Log tab.

**What to look for:**
- Confirm an `enforcement.applied` event exists in the timeline with `action: block`.
- Audit log: verify the enforcement action record matches the session timestamp and tool name.
- Confirm `tool_name` is an AI tool listed in your monitored tool classes. A block on a non-AI system process is a false positive.
- Check `confidence_band` and `risk_signals` to confirm the block threshold was met legitimately.

**Suggested verdict:**
- If the blocked process is confirmed as an AI tool with matching risk signals — block is valid. Log confirmation in the audit note.
- If the block fired on a non-AI process (false positive) — navigate to Enforcement → Allow List → add the process to the allow-list. Document the entry with the session ID and reason. Review the policy rule that triggered the block and adjust the `tool_classes` condition to exclude the affected class.

---

### Scenario 4: Capability drift alert

**What triggers it:** An event arrives with `agent_status.capability_drift` present in the payload. This indicates a telemetry source has disappeared — for example, `file_read` events have stopped arriving from an endpoint that was previously emitting them.

**Dashboard path:** Endpoints → select endpoint → check agent status indicator → Events tab → verify last event timestamps per event type.

**What to look for:**
- Which event type has dropped off (e.g., `file_read`, `network`, `process_exec`).
- When the last event of that type was received.
- Whether other event types from the same endpoint are still flowing (partial vs. full loss).
- Agent health: check the endpoint's agent version, last heartbeat, and OS permissions status.

**Suggested verdict:**
- Do not change policy based on capability drift alone.
- Create an incident note in the audit log with: endpoint ID, affected event type, timestamp of last event, and observed symptoms.
- Assign an agent health investigation to the endpoint owner or ops team. Refer to [docs/macos-permissions.md](macos-permissions.md) or [docs/macos-install-failure-notes.md](macos-install-failure-notes.md) for permission recovery steps.
- If drift persists after agent restart, escalate to engineering per the [Escalation Path](#escalation-path).

---

## API Quick Reference

| Task | curl command |
|---|---|
| List recent sessions | `curl -H "X-API-Key: $KEY" "https://<host>/api/sessions?limit=20&observed_after=<ISO8601>"` |
| Get session detail | `curl -H "X-API-Key: $KEY" "https://<host>/api/sessions/<session_id>"` |
| List events for an endpoint | `curl -H "X-API-Key: $KEY" "https://<host>/api/events?endpoint_id=<endpoint_id>&limit=50"` |
| Check audit log | `curl -H "X-API-Key: $KEY" "https://<host>/api/audit-log?limit=50"` |
| Add allow-list entry | `curl -X POST -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"process_name":"<name>","reason":"<reason>"}' "https://<host>/api/enforcement/allowlist"` |

Replace `<host>`, `$KEY`, and parameter values with your environment specifics. All timestamps are ISO 8601 UTC.

---

## Escalation Path

Loop in engineering when any of the following are true:

- **Unexplained confidence drop >20%** — a tool's `confidence_score` drops more than 20 points between consecutive sessions with no change in behavior. This may indicate a calibration regression or scoring pipeline issue.
- **Enforcement fired on a non-AI process** — after allow-listing the process, document the session ID and the rule that triggered enforcement, and open an engineering ticket to audit the `tool_classes` condition.
- **Zero events after confirmed AI tool is running** — the tool is verified running on the endpoint (confirmed by OS process list) but no events have arrived for more than 15 minutes. This is distinct from capability drift; it may indicate agent crash, network block, or API ingestion failure.
- **Schema errors in event payload** — the dashboard or API returns a parse error or shows malformed fields in the event timeline. Capture the raw event payload from `GET /api/events` and provide it to engineering.

Do not adjust policy to work around schema errors or zero-event conditions. These are infrastructure faults.

---

## Common False Positive Patterns

| Trigger | Why it's a false positive | Mitigation |
|---|---|---|
| Dev tooling (`npm`, `pip`, `cargo`) detected as AI tool activity | Package managers make network connections and write to disk in patterns that overlap with AI tool behavior signatures. They are not AI tools. | Add the process to the allow-list (Enforcement → Allow List). Refine the `tool_classes` condition on the triggering rule to exclude Class B processes if applicable. |
| CI/CD runner detected during automated build | Build agents run exec + write + network sequences at high frequency. On shared endpoints, these sequences can score at Medium or High confidence. | Use endpoint tagging to mark CI runners. Apply a scoped policy rule that downgrades decisions for tagged endpoints during known build windows. |
| Agent telemetry event misattributed to monitored tool | If two processes share a parent PID or are spawned in close sequence, event grouping can attribute one process's actions to another tool's session. | Review the `strongest_subchain` in the session detail for unexpected process names. Open an incident note and escalate to engineering to review session grouping logic. |

---

Related: [docs/pilot-runbook.md](pilot-runbook.md) | [docs/pilot-go-no-go-checklist.md](pilot-go-no-go-checklist.md) | [docs/known-limitations.md](known-limitations.md)
