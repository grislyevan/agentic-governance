# Agent Session Reconstruction Engine — Project Setup

## Goal

Add an **Agent Session Reconstruction Engine** that produces full timeline narratives per agent session, not just behavior chains or aggregate counts. Security teams see an ordered list of actions with timestamps, for example:

```
Agent Session
Tool: Cursor

13:04:02 LLM request
13:04:05 bash npm install
13:04:11 write package.json
13:04:15 git commit
13:04:21 npm test
```

This feature makes Detec instantly compelling to security teams. The architecture already supports it: EventStore (process, file, network events with timestamps and PIDs), process trees, and session reports exist; the missing piece is timeline reconstruction and surfacing.

## Key takeaway

The system already has: EventStore with ProcessExecEvent, FileChangeEvent, NetworkConnectEvent (timestamps, PID, cmdline, path, action, remote_addr); process trees (build_trees, get_all_pids) so a tool's PIDs can be expanded to the full tree; session reports (aggregate counts and risk signals); correlation mapping tools to trees; and detection event payloads stored in full by the API. The only missing piece is a **timeline reconstruction** step: EventStore + tool PIDs to a sorted list of (timestamp, label, type) entries, then attach that list to the session report and detection event payload.

## Scope

1. **Timeline reconstruction (collector):** New module that, given EventStore, tool name, and tool PIDs (optionally expanded to full process tree), gathers process/network/file events for those PIDs, merges and sorts by timestamp, and converts each to a normalized timeline entry: at (time), label (short human string), type (e.g. llm, shell_exec, file_write, file_delete, network). Labels: shell exec to "bash &lt;cmd&gt;" or process name; file to "write/delete/modified &lt;basename&gt;"; network to LLM hosts as "LLM request" else "connect to &lt;host&gt;". Cap length (e.g. 50–100 entries). Reuse existing LLM host patterns and shell name sets.

2. **Collector integration:** For each detected scan, compute PIDs (extract from evidence; optionally expand to tree via build_trees + get_all_pids). Call timeline reconstruction. Pass timeline into session report building and into the detection.observed event payload (new optional top-level key session_timeline). Session report data model gains an optional timeline field; CLI prints the narrative (HH:MM:SS label) when present.

3. **API:** Allow session_timeline in event payload (event validator whitelist). Session report schema gains optional session_timeline (list of at, label, type). Session aggregation: when building a session report from events, if any event in the group has payload.session_timeline, attach it to the report (e.g. from the most recent event in the group).

4. **Dashboard:** When displaying a session report, show the timeline when present (list or compact narrative). No new API contract; timeline is part of existing session report response.

## Required behavior

- Collector can produce a per-tool, time-ordered list of human-readable actions (LLM request, bash &lt;cmd&gt;, write &lt;file&gt;, git commit, etc.) from EventStore telemetry for that tool's PIDs (or tree).
- Timeline appears in collector session report CLI output and is included in detection.observed payload so the API stores it.
- API accepts and stores session_timeline in event payloads; GET session-reports returns session_timeline when present in stored events.
- CLI and dashboard can display the narrative (timestamp + label per line).

## Out of scope

- New telemetry providers or new event types.
- Changing confidence engine or detection logic.
- Real-time streaming timelines; batch/on-demand is sufficient.

## Non-goals / future

- Cross-session or cross-tool timeline merging.
- Editing or annotating timeline entries.
