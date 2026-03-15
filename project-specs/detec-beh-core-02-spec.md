# DETEC-BEH-CORE-02 — Agentic Read-Modify-Write Loop (Implementation Spec)

## Intent

Detect interleaved file reads/writes and network activity to a model provider or local inference service, occurring in short cycles and tied to a coherent process tree. Proves the endpoint is actively using an AI tool to change code, not just running it.

## Internal pattern

BEH-004 (Read-modify-write loop) in `collector/scanner/behavioral_patterns.py`.

## Trigger conditions

- Multiple file events (read/modify/write) and network events in the same process tree.
- File–network–file transitions occur within a cycle window; at least N full cycles in that window.
- Network activity is model-related (LLM API host or local inference port) so the loop is tied to model use.

## Telemetry required

- File events: path, action (created/modified), timestamp, pid.
- Network events: remote_addr, remote_port, sni, pid.
- Process tree for correlation.

## Thresholds (explicit)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `rmw_loop_window_seconds` | 10 | Cycle window (seconds) for one file–net–file cycle. |
| `rmw_loop_min_cycles` | 2 | Minimum complete cycles to trigger. |

Scoring: linear interpolation from `min_cycles` (0.5) to 4 (0.8) to 6 (1.0) cycles.

## Confidence and penalties

- Confidence: BEH-004 score contributes to file, network, and behavior layers. Aggregated with other patterns.
- Penalties: same as other behavioral (e.g. `behavioral_only_no_file_artifact` when no file evidence elsewhere).

## Evidence output (schema)

- `cycles_detected`: number of file–net–file cycles
- `cycle_window_seconds`: window used
- Affected directories/files (from file events in cycles)
- Model destination or local inference endpoint (from network events in cycles)
- Process ancestry: root name, pid

## Sample event output

```json
{
  "behavioral_patterns": [{
    "pattern_id": "BEH-004",
    "pattern_name": "Read-modify-write loop",
    "score": 0.8,
    "evidence": {
      "cycles_detected": 4,
      "cycle_window_seconds": 10,
      "affected_directories": ["/project/src", "/project/lib"],
      "model_endpoint": "api.anthropic.com:443"
    }
  }],
  "root_process": { "pid": 5678, "name": "cursor", "cmdline": "Cursor" }
}
```

## Expected false positives

- Normal editing with occasional API calls: one or two file–net–file sequences. Mitigation: `rmw_loop_min_cycles` >= 2 and short window so sustained loops are required.
- IDE auto-save plus background sync. Mitigation: require model-related network (LLM host or local inference), not arbitrary outbound.

## Analyst summary (target)

"Agentic read-modify-write loop detected: M file–model cycles in W seconds affecting directories D, tied to process P."
