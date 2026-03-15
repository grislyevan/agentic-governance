# Agent Session Reconstruction Engine — Technical Architecture

For implementers. Source: [project-specs/agent-session-reconstruction-setup.md](../project-specs/agent-session-reconstruction-setup.md) and [task list](../project-tasks/agent-session-reconstruction-tasklist.md).

---

## 1. Data flow

- **Collector:** EventStore (process, network, file events) + tool PIDs from scan evidence → optional tree expansion (build_trees, get_all_pids) → timeline reconstruction → list of `{ at, label, type }` → attached to SessionReportData and to detection.observed payload as `session_timeline`.
- **API:** Event payload (with optional `session_timeline`) stored in `Event.payload`. Session aggregation builds SessionReport from event groups; when any event in the group has `payload.session_timeline`, attach it to the report (e.g. from the most recent event). GET session-reports returns reports with `session_timeline` when present.

---

## 2. Timeline entry shape

- **at:** string, time only (e.g. `HH:MM:SS`) or ISO8601; keep small for display.
- **label:** string, short human-readable (e.g. "LLM request", "bash npm install", "write package.json").
- **type:** string, one of: `llm`, `shell_exec`, `file_write`, `file_delete`, `file_modified`, `network` (or similar).

Cap list length (e.g. 50–100 entries) to avoid oversized payloads; validator allows depth and key limits.

---

## 3. Timeline reconstruction (collector)

- **Module:** e.g. `collector/engine/session_timeline.py`.
- **Input:** EventStore, tool_name (for logging), tool_pids (set[int]). Optional: expand_tree (bool); when True, use build_trees(store), find trees that intersect tool_pids, then union of get_all_pids(tree) for those trees.
- **Gather events:** get_process_events(), get_network_events(), get_file_events(). Filter to events where event.pid is in the (possibly expanded) PID set. File events may have pid=None; include only when pid is in set.
- **Label rules:**
  - ProcessExecEvent: if name (basename) in shell set (bash, sh, zsh, ...) → label = first token of cmdline or "bash &lt;cmd&gt;" (truncate to e.g. 80 chars). Else label = process name or truncated cmdline. type = "shell_exec" for shells else "exec".
  - FileChangeEvent: action "created" or "modified" → "write &lt;basename&gt;", type "file_write"; "deleted" → "delete &lt;basename&gt;", type "file_delete". Use os.path.basename(path).
  - NetworkConnectEvent: if remote_addr or sni matches known LLM host patterns (anthropic, openai, ollama, etc.) → "LLM request", type "llm"; else "connect to &lt;host&gt;" (truncate), type "network".
- **Sort** by event timestamp; convert to list of dicts; cap length (e.g. 100). Return list.

Reuse: `_SHELL_NAMES`, `_LLM_HOST_PATTERNS` from collector/session_report.py or collector/telemetry/event_store.py; build_trees, get_all_pids from collector/scanner/process_tree.py.

---

## 4. Collector integration points

- **Orchestrator:** After _collect_scan_results and behavioral/evasion/MCP scans, for each scan in detected_scans: (1) pids = _extract_pids(scan). (2) Optionally tree_pids = union of get_all_pids(t) for trees that intersect pids (build_trees(event_store)). (3) timeline = build_session_timeline(event_store, scan.tool_name, tree_pids or pids, expand_tree=True/False). (4) When calling build_session_reports, pass per-tool timelines (e.g. dict tool_name -> timeline). (5) When calling build_event for detection.observed, pass session_timeline=timeline.
- **SessionReportData:** Add field `timeline: list[dict] | None` (list of { at, label, type }). build_session_reports: accept optional argument tool_timelines: dict[str, list] and attach timeline to each report by tool.
- **build_event:** Add optional parameter session_timeline: list | None; when present, event["session_timeline"] = session_timeline.

---

## 5. API changes

- **Event validator** (api/core/event_validator.py): Add `"session_timeline"` to _ALLOWED_TOP_LEVEL_KEYS. Optionally validate that session_timeline is a list of objects with at, label, type (and size/depth within limits).
- **SessionReport schema** (api/schemas/session_report.py): Add SessionTimelineEntry (at: str, label: str, type: str). Add session_timeline: list[SessionTimelineEntry] | None to SessionReport.
- **Session aggregation** (api/core/session_aggregation.py): In aggregate_events_into_sessions, when building each SessionReport, if any event in the group has payload.get("session_timeline"), set report.session_timeline (e.g. from the last event in the group that has it, or the event with the longest timeline).

---

## 6. CLI and dashboard

- **CLI** (format_session_report_for_cli): If report.timeline is non-empty, after "top behavior chains" (or in place) print "timeline:" and then one line per entry: "  HH:MM:SS label".
- **Dashboard:** In the view that shows session report details, if session_timeline is present, render it (e.g. list or preformatted lines). No new API; field is part of SessionReport.

---

## 7. Edge cases

- No PIDs (scheduler-only detection): timeline = [] or skip timeline for that report.
- Behavioral "Unknown Agent": use tree PIDs from the matched behavioral tree.
- Label truncation: cmdline and path to basename; cap label length (e.g. 120 chars) to stay within payload limits.
