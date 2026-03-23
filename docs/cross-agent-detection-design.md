# Cross-Agent Behavior Detection — Design

**Workstream 3.** Design for detecting "agent A calls agent B" and multi-agent workflows so the SOC can see chained or coordinated agent use, not only individual tools.

## Current behavior

- **Detection entry:** [collector/main.py](../collector/main.py) `run_scan()` runs named scanners (Claude Code, Cursor, etc.) and the behavioral scanner, then calls `_process_detection()` for each detection.
- **Per-detection pipeline:** One event per tool; no field for "related" tools or multi-agent workflow.
- **Behavioral scanner:** [collector/scanner/behavioral.py](../collector/scanner/behavioral.py) finds "Unknown Agent" (Class C) by process-tree patterns; it excludes PIDs already claimed by named scanners. It does not correlate multiple known tools in the same tree or time window.
- **Event payload:** Events have `tool_name`, `tool_class`, `confidence`, `signals`; no `correlation_context` or `related_tool_names`.

## Goals

1. Detect when two or more known agent tools (or one known + behavioral "Unknown Agent") appear in the same process tree or in the same short time window.
2. Expose that to the SOC via event payload or a dedicated observation type.
3. Keep existing single-tool detection and events unchanged; add correlation as an optional layer.

## Data available

- **After Stage 1:** `detected_scans` (list of `ScanResult` with `tool_name`, `signals`, PIDs from scan), `detected_tools` (set of tool names), and the behavioral scan result if any.
- **Event store:** [collector/telemetry/event_store.py](../collector/telemetry/event_store.py) holds process events (PID, PPID, name, cmdline, timestamp). Process trees can be built via [collector/scanner/process_tree.py](../collector/scanner/process_tree.py).
- **PIDs:** Each `ScanResult` can carry PIDs (e.g. from `scan.signals` or scanner-specific extraction). main.py uses `_extract_pids(scan)` for container check and enforcement.

## Proposed approach

### Option A: Correlation context on existing event (recommended for MVP)

- After collecting all `detected_scans` (and behavioral) in a cycle, run a **correlation step**: build the process tree from the event store, and for each detection check if any other detected tool’s PIDs appear in the same tree (ancestor or descendant) or within a small time window (e.g. same 60s).
- If correlation found, attach to each affected event an optional field, e.g. `correlation_context: { "multi_agent": true, "related_tool_names": ["Cursor", "Open Interpreter"] }`.
- **Event schema:** Add optional `correlation_context` (object) to the canonical event schema; dashboard and API can ignore or display it.

### Option B: Separate cross-agent observation event

- Emit a second event type (e.g. `cross_agent_observation`) when two or more tools are correlated, with `primary_tool`, `secondary_tools`, `relationship` (e.g. same_tree, same_window). Requires schema and API/dashboard support for the new type.

**Recommendation:** Start with Option A so no new event type is needed; if the SOC needs a dedicated view, add Option B later.

## Correlation logic (minimal)

1. **Same tree:** For each pair of detections (A, B), get PIDs for A and B. If any PID of A is ancestor or descendant of any PID of B in the process tree built from the event store, mark (A, B) as correlated.
2. **Same window:** If A and B have events within the last N seconds (e.g. 60) and no tree overlap, optionally mark as weak correlation (e.g. `same_window` only).
3. **Output:** For each detection, set `related_tool_names = [names of other detected tools that are correlated]`. If non-empty, set `multi_agent: true` in correlation_context.

## Implementation notes

- **Where:** New function in collector (e.g. `engine/correlation.py` or in main.py) that takes `detected_scans`, `event_store`, and returns a mapping `tool_name -> list[related_tool_names]`. main.py calls it after Stage 1 and passes the result into the event payload when emitting.
- **Tests:** Unit tests with a small event store and two ScanResults whose PIDs form a parent/child; assert correlation_context present. Integration test: run_scan with two tools running (or mocked) and assert at least one event has correlation_context.
- **Performance:** Correlation step is O(detections^2) × tree lookup; tree build is already done for behavioral scanner. Acceptable for typical endpoint with few concurrent tools.

## Playbook / INIT

- Add a short playbook subsection (or INIT) on "Multi-agent and chained agent threats" that references this design and the new event field. Detection profiles can note when a tool is often used with another (e.g. Cursor + MCP servers).
