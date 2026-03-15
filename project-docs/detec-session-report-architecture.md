# Detec Session Report — Technical Architecture

For implementers. Source: [project-specs/detec-session-report-setup.md](../project-specs/detec-session-report-setup.md) and [task list](../project-tasks/detec-session-report-tasklist.md).

---

## 1. Session report data model

### 1.1 Canonical structure

- **tool**: string (tool name, e.g. "Claude Cowork")
- **duration_seconds**: int (session length)
- **started_at**: ISO8601 datetime (first event in session)
- **ended_at**: ISO8601 datetime (last event in session)
- **endpoint_id**: string (optional; for API responses)
- **actions**: object with optional counts (when available):
  - **file_reads**: int or null (N/A when no telemetry)
  - **file_writes**: int or null
  - **shell_commands**: int or null
  - **model_calls**: int or null
- **actions_note**: string, optional (e.g. "Counts from endpoint telemetry" or "N/A: detection-only aggregation")
- **risk_signals**: list of human-readable strings (e.g. "credential access", "repo modification")

### 1.2 Session boundaries (API)

- Group stored `Event` rows by `(tenant_id, endpoint_id, tool_name)`.
- Sort by `observed_at`. Consecutive events for the same group within a configurable window (e.g. 10–15 minutes) belong to the same session. Gap larger than window starts a new session.
- Session **started_at** = min(observed_at) in the group; **ended_at** = max(observed_at); **duration_seconds** = (ended_at - started_at).total_seconds().

### 1.3 Session boundaries (collector)

- One "current" session per run: time window = event store retention (e.g. last 120 seconds). started_at / ended_at from first and last telemetry event timestamp for the detected tool's PIDs (or scan cycle time if no telemetry).

---

## 2. Risk signal mapping (no new taxonomy)

Derive human-readable labels from existing event payload fields:

| Source | Example mapping |
|--------|------------------|
| `action.type` == "repo" | "repo modification" |
| `action.risk_class` R3/R4 + context | higher-risk; combine with type for label |
| `mitre_attack.techniques[].tactic` | "Credential Access" → "credential access", "Collection" → "data collection", "Execution" → "execution", "Exfiltration" → "exfiltration", "Persistence" → "persistence", "Command and Control" → "command and control" |
| Behavioral pattern IDs (from evidence) | BEH-006 → "credential access", BEH-007 → "repo modification" / "git automation" |

Implementation: single function that accepts event payload (or scan result) and returns list of normalized risk signal strings (lowercase, deduplicated).

---

## 3. Action counts

- **API (MVP):** Stored events do not contain per-action counts. Return `file_reads`, `file_writes`, `shell_commands`, `model_calls` as null or 0 and set `actions_note` to "N/A: aggregated from detection events only" (or similar).
- **Collector:** Use event store: `FileChangeEvent` (action "created" or "modified") → file_writes; `ProcessExecEvent` with name in shell list → shell_commands; `NetworkConnectEvent` to known LLM host patterns → model_calls. File reads: if telemetry supports read events, count them; else 0 or N/A. Duration from oldest to newest event in store for the relevant PIDs, or scan window.

---

## 4. API endpoint

- **GET /api/endpoints/{endpoint_id}/session-reports**  
  Query params: `since` (datetime), `before` (datetime), `limit` (default 50). Returns list of session reports for that endpoint (tenant-scoped). Sessions derived from events with `event_type == "detection.observed"` (or equivalent).

- **GET /api/session-reports**  
  Query params: `endpoint_id`, `since`, `before`, `limit`. Same response shape; filter by endpoint when provided.

Response shape: `{ "items": [ SessionReport, ... ] }` where SessionReport matches the canonical structure above.

---

## 5. Collector output

- **CLI:** New subcommand `detec-agent session-report` (or flag `--session-report` after scan). After running scanners (and optionally a scan), build one session report from current event store + scan results for detected tools. Print the example format:

```
Agent Session Detected

tool: <tool_name>
duration: <X>m<Y>s

actions:
- N file reads
- N file writes
- N shell commands
- N model calls

risk signals:
- <label1>
- <label2>
```

- If multiple tools detected, either one report per tool or one combined (spec: single-tool sessions for MVP; one report per detected tool is acceptable).

---

## 6. Dashboard (optional)

- Consume GET /api/endpoints/{id}/session-reports (or /api/session-reports). Display table or cards: tool, duration, action counts (or N/A), risk signals. No new API contracts.

---

## 7. Validation (for QA)

- **API:** Create events for same endpoint + tool within 10 minutes; call session-reports endpoint; assert one session with correct duration and at least one risk signal when payload contains action.type or mitre_attack.
- **Collector:** Run with telemetry (or mocked event store) and --session-report; assert output contains "Agent Session Detected", tool name, duration, actions block, risk signals block.
- **Risk mapping:** Unit test: payload with action.type "repo" and technique "Credential Access" yields "repo modification" and "credential access" in risk_signals.
