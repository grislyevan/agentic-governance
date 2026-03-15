# DETEC-BEH-CORE-01 — Autonomous Shell Fan-Out (Implementation Spec)

## Intent

Detect a session where a likely agent parent process causes repeated shell child creation within a bounded time window, optionally with repo or file activity. This is the clearest signal of autonomous execution on a developer machine.

## Internal pattern

BEH-001 (Shell fan-out) in `collector/scanner/behavioral_patterns.py`.

## Trigger conditions

- Parent process or tree is associated with agentic behavior or LLM activity (e.g. BEH-002 LLM cadence present in same tree), OR tree is unscanned by named tools (Unknown Agent path).
- Child shell count in a sliding time window exceeds threshold.
- Shells are direct or indirect children of the tree root; cadence suggests automation rather than manual use (many shells in short window).

## Telemetry required

- Process telemetry: parent/child process tree, process names, start times.
- Optional: file events for repo modification corroboration.

## Thresholds (explicit)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `shell_fanout_window_seconds` | 60 | Sliding window (seconds) for counting shell children. |
| `shell_fanout_min_children` | 5 | Minimum shell children in any window span to trigger. |

Scoring: linear interpolation from `min_children` (0.5) to 8 (0.8) to 12 (1.0) shells in window.

## Confidence and penalties

- Confidence: BEH-001 score (0.0–1.0) contributes to behavior layer; aggregated with other pattern scores and layer weights (Unknown Agent: `BEHAVIORAL_WEIGHTS` in `engine/confidence.py`).
- Penalties: `behavioral_only_no_file_artifact` (0.15) if process + network but no file evidence. `weak_identity_correlation` (0.10) if identity signal below threshold.

## Evidence output (schema)

- `root_process`: pid, name, cmdline
- `shell_children_in_window`: count
- `window_seconds`: window used
- `shell_names`: sample (e.g. first 10)
- Optional: `sample_commands`, `timestamps` from process nodes when available

## Sample event output

```json
{
  "behavioral_patterns": [{
    "pattern_id": "BEH-001",
    "pattern_name": "Shell fan-out",
    "score": 0.8,
    "evidence": {
      "shell_children_in_window": 8,
      "window_seconds": 60,
      "shell_names": ["bash", "bash", "zsh", "bash", ...]
    }
  }],
  "root_process": { "pid": 1234, "name": "node", "cmdline": "node agent.js" }
}
```

## Expected false positives

- Heavy manual terminal use: many short-lived shells (e.g. loops, parallel invocations). Mitigation: require LLM activity in tree (BEH-002) for full score or treat as agent-linked; otherwise aggregate score may stay below detection threshold when only BEH-001 fires.
- Build scripts or CI-like activity on the host. Mitigation: `behavioral_only_no_file_artifact` penalty and detection_threshold (0.45) limit standalone process+network-only trees.

## Analyst summary (target)

"Autonomous shell execution pattern detected: N shell children spawned from a model-linked parent process over W seconds, with repo modification activity observed."
