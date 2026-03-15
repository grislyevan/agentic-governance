# Agent Session Reconstruction Engine — Task List

Source: [project-specs/agent-session-reconstruction-setup.md](../project-specs/agent-session-reconstruction-setup.md)

## Quoted requirements from spec

- **Goal:** "Add an Agent Session Reconstruction Engine that produces full timeline narratives per agent session... Security teams see an ordered list of actions with timestamps (e.g. 13:04:02 LLM request, 13:04:05 bash npm install, 13:04:11 write package.json)."
- **Timeline reconstruction:** "Given EventStore, tool name, and tool PIDs (optionally expanded to full process tree), gathers process/network/file events for those PIDs, merges and sorts by timestamp, and converts each to a normalized timeline entry: at (time), label (short human string), type (e.g. llm, shell_exec, file_write, file_delete, network). Cap length (e.g. 50–100 entries). Reuse existing LLM host patterns and shell name sets."
- **Collector integration:** "For each detected scan, compute PIDs (extract from evidence; optionally expand to tree via build_trees + get_all_pids). Call timeline reconstruction. Pass timeline into session report building and into the detection.observed event payload (new optional top-level key session_timeline). Session report data model gains an optional timeline field; CLI prints the narrative (HH:MM:SS label) when present."
- **API:** "Allow session_timeline in event payload (event validator whitelist). Session report schema gains optional session_timeline (list of at, label, type). Session aggregation: when building a session report from events, if any event in the group has payload.session_timeline, attach it to the report (e.g. from the most recent event in the group)."
- **Dashboard:** "When displaying a session report, show the timeline when present. No new API contract; timeline is part of existing session report response."
- **Out of scope:** "New telemetry providers or new event types; changing confidence engine or detection logic."

---

## Tasks

### [x] Task 1: Timeline reconstruction module (collector)

- **What:** New module (e.g. collector/engine/session_timeline.py) that builds a session timeline from EventStore and tool PIDs. Input: EventStore, tool_name, tool_pids. Optionally expand PIDs to full tree using build_trees(store) and get_all_pids(tree). Gather process, network, and file events filtered by PID set; convert each to a timeline entry (at, label, type); sort by timestamp; cap at 50–100 entries. Label rules: ProcessExecEvent for shells to "bash &lt;cmd&gt;" or process name; FileChangeEvent to "write/delete/modified &lt;basename&gt;"; NetworkConnectEvent to "LLM request" for known LLM hosts else "connect to &lt;host&gt;". Reuse LLM host patterns and shell name set from session_report or event_store.
- **Acceptance criteria:**
  - [x] Function exists and returns list of timeline entries (at, label, type) sorted by time.
  - [x] PID filtering and optional tree expansion work; empty PIDs yields empty or whole-window behavior per spec.
  - [x] Unit tests: mock EventStore, assert order and label content (shell, LLM, file).
- **Status:** done

---

### [x] Task 2: Collector — Session report and event payload integration

- **What:** In orchestrator, after scans and correlation: for each detected scan get PIDs (and optionally expand to tree PIDs), call timeline reconstruction, pass timeline into build_session_reports and into build_event. Add optional timeline field to SessionReportData; build_session_reports accepts/attaches per-tool timelines. In build_event add optional session_timeline parameter and include it in the event dict when present.
- **Acceptance criteria:**
  - [x] Session reports (collector) include timeline when telemetry and PIDs available.
  - [x] detection.observed payload includes session_timeline when provided; no break to existing callers.
  - [x] Integration test or manual run: scan with seeded event store produces timeline in report and in emitted event.
- **Status:** done

---

### [x] Task 3: Collector — CLI timeline output

- **What:** In format_session_report_for_cli (session_report.py), when report.timeline is non-empty, print a "timeline" section with one line per entry: HH:MM:SS label (matching the example in the spec).
- **Acceptance criteria:**
  - [x] CLI session report output shows timeline lines when timeline present.
  - [x] No regression when timeline is None or empty.
- **Status:** done

---

### [x] Task 4: API — Event validator and session report schema

- **What:** Add "session_timeline" to allowed top-level keys in event validator. Add SessionTimelineEntry model (at, label, type) and optional session_timeline on SessionReport in api/schemas/session_report.py. In session_aggregation, when building each SessionReport from a group of events, set session_timeline from payload of one event in the group (e.g. most recent event that has session_timeline).
- **Acceptance criteria:**
  - [x] POST /api/events with session_timeline is accepted and stored.
  - [x] GET session-reports returns session_timeline in report when present in stored events.
  - [x] Existing session report tests still pass; add test for timeline in payload and in response.
- **Status:** done

---

### [ ] Task 5: Dashboard — Show timeline in session report view (optional)

- **What:** Where session reports are displayed, render session_timeline when present (e.g. list of "at label" or compact narrative).
- **Acceptance criteria:**
  - [ ] At least one session report view shows timeline when data includes it.
  - [ ] Data comes from existing session reports API (no new endpoint).
- **Status:** pending

---

## Completion

- Tasks 1–4 are required for MVP (timeline reconstruction, collector integration, CLI, API). Task 5 (dashboard) is optional; spec says "when displaying a session report, show the timeline when present."
