# Detec Session Report — Project Setup

## Goal

Add an **agent session report** that makes the system feel more intelligent by surfacing time-bounded, tool-attributed summaries of agent activity: tool name, duration, action counts (file reads, file writes, shell commands, model calls), and risk signals (e.g. credential access, repo modification). This pushes Detec toward **agent session understanding**, a category most security tools do not yet address.

## Key takeaway

The architecture already does the hard part: **multi-layer behavioral correlation** (process tree, telemetry event store, confidence engine, correlation_context). The session report builds on that by aggregating over a session window and presenting a concise, human-readable summary.

## Required output format (example)

```
Agent Session Detected

tool: Claude Cowork
duration: 4m18s

actions:
- 53 file reads
- 8 file writes
- 3 shell commands
- 2 model calls

risk signals:
- credential access
- repo modification
```

## Scope

1. **Session definition:** A session is a time-bounded period of attributed agent activity on one endpoint for one tool. Session boundaries can be derived from: (a) consecutive detection events for the same tool on the same endpoint within a configurable window (e.g. 10–15 minutes), or (b) first-to-last telemetry timestamp for that tool’s PIDs in the event store over the retention window. MVP may use (a) with API-stored events; collector can later emit session summaries using (b).

2. **Action counts:** File reads, file writes, shell commands, model calls. Sources: telemetry (ProcessExecEvent for shells, FileChangeEvent for writes; file reads if available or inferred), network events to known LLM endpoints for model calls. When telemetry is not available (e.g. polling-only), use evidence from scan results (e.g. behavioral pattern counts, artifact hints) to approximate or report "N/A" with a short reason.

3. **Risk signals:** Short, human-readable labels such as "credential access", "repo modification". Derived from existing fields: action_risk (R1–R4), behavioral patterns (e.g. BEH-*), action_type (exec, repo, etc.), and any existing attack mapping (MITRE). No new risk taxonomy; map existing schema to display labels.

4. **Surfaces:** At least one of: (a) API endpoint that returns session report(s) for an endpoint or time range, (b) collector CLI subcommand or output that prints a session report for the current or last session, (c) dashboard view that shows session reports. Delivering (a) plus (b) or (c) is sufficient for MVP.

## Out of scope

- Changing confidence engine weights or detection logic.
- New telemetry providers or new event types (use existing ProcessExecEvent, FileChangeEvent, NetworkConnectEvent).
- New risk taxonomy; reuse action_risk, action_type, and behavioral/attack mapping.

## Non-goals / future

- Real-time streaming session reports; batch or on-demand is sufficient for MVP.
- Cross-tool sessions (e.g. "Cursor then Claude"); single-tool sessions only for MVP.
