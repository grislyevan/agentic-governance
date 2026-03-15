# Detec Session Report — Task List

Source: [project-specs/detec-session-report-setup.md](../project-specs/detec-session-report-setup.md)

## Quoted requirements from spec

- **Goal:** "Add an agent session report that makes the system feel more intelligent by surfacing time-bounded, tool-attributed summaries of agent activity: tool name, duration, action counts (file reads, file writes, shell commands, model calls), and risk signals (e.g. credential access, repo modification)."
- **Session definition:** "A session is a time-bounded period of attributed agent activity on one endpoint for one tool. Session boundaries: (a) consecutive detection events for the same tool on the same endpoint within a configurable window (e.g. 10–15 minutes), or (b) first-to-last telemetry timestamp for that tool's PIDs in the event store. MVP may use (a) with API-stored events; collector can later emit session summaries using (b)."
- **Action counts:** "File reads, file writes, shell commands, model calls. Sources: telemetry (ProcessExecEvent for shells, FileChangeEvent for writes; file reads if available or inferred), network events to known LLM endpoints for model calls. When telemetry is not available, use evidence from scan results to approximate or report 'N/A' with a short reason."
- **Risk signals:** "Short, human-readable labels (e.g. credential access, repo modification). Derived from existing fields: action_risk (R1–R4), behavioral patterns, action_type (exec, repo, etc.), and existing attack mapping. No new risk taxonomy."
- **Surfaces:** "At least one of: (a) API endpoint that returns session report(s) for an endpoint or time range, (b) collector CLI subcommand or output that prints a session report for the current or last session, (c) dashboard view. Delivering (a) plus (b) or (c) is sufficient for MVP."
- **Out of scope:** "Changing confidence engine weights or detection logic; new telemetry providers or new event types; new risk taxonomy."

---

## Tasks

### [x] Task 1: Define session report data model and risk-label mapping

- **What:** Add a canonical session report schema (tool name, duration_seconds, started_at, ended_at, action counts: file_reads, file_writes, shell_commands, model_calls, risk_signals list). Define mapping from existing event/scan fields (action_risk, action_type, behavioral pattern IDs, MITRE techniques) to human-readable risk signal labels (e.g. R3 + repo → "repo modification"; credential-related technique → "credential access").
- **Acceptance criteria:**
  - [x] Session report structure is documented (e.g. in schemas/ or project-docs) and usable by API and collector.
  - [x] Risk label mapping covers at least: credential access, repo modification, and maps from existing action_risk/action_type/techniques.
- **Status:** done

---

### [x] Task 2: API — Session aggregation from stored events

- **What:** Implement server-side session detection: group stored detection events by (endpoint_id, tool_name) and time window (e.g. events within 10–15 minutes belong to same session). Compute per-session: duration (first to last event), action counts from event payloads if available (or placeholder 0/N/A with reason), risk signals from action.risk_class, action.type, and mitre_attack.techniques. Expose at least one endpoint: e.g. GET /api/endpoints/{id}/session-reports or GET /api/session-reports?endpoint_id=&since=.
- **Acceptance criteria:**
  - [x] Sessions are derived from consecutive events for same tool + endpoint within configurable window.
  - [x] Endpoint returns session report(s) with tool, duration, action counts (or N/A), risk_signals.
  - [x] No change to event ingestion or confidence logic.
- **Status:** done

---

### [x] Task 3: Collector — Session summary from telemetry (current window)

- **What:** In the collector, add logic to build a session report for the current retention window: use event store (ProcessExecEvent, FileChangeEvent, NetworkConnectEvent) to count shell commands, file writes, file reads (if available), and model calls (network to known LLM endpoints). Use scan result(s) for the detected tool to get tool name, and optional risk signals from action_risk/behavioral evidence. Emit or expose this as: (a) a CLI subcommand or flag (e.g. `detec-agent session-report` or `--session-report` after scan), or (b) include session summary in existing scan output. Output format matches the example (tool, duration, actions, risk signals).
- **Acceptance criteria:**
  - [x] Collector can produce a session report for the current/last window using telemetry and scan results.
  - [x] CLI prints the example-style output (tool, duration, actions, risk signals).
  - [x] When telemetry lacks data, action counts show N/A or 0 with brief reason where appropriate.
- **Status:** done

---

### [ ] Task 4: Dashboard — Session reports view (optional for MVP)

- **What:** Add a dashboard view that displays session reports: e.g. list of sessions for selected endpoint with tool, duration, action counts, risk signals. Data from API endpoint from Task 2.
- **Acceptance criteria:**
  - [ ] At least one screen or panel shows session report data (tool, duration, actions, risk signals).
  - [ ] Data is loaded from the session reports API.
- **Status:** pending

---

## Completion

- Tasks 1, 2, and 3 are required for MVP (session model + API + collector CLI). Task 4 (dashboard) is optional; delivering (a) plus (b) per spec means Task 2 + Task 3 must pass QA. Task 4 may be deferred.
