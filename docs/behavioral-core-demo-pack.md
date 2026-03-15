# Detec Core Behavioral Detection Demo Pack

This doc provides a single demo flow for the four core behavioral detections (DETEC-BEH-CORE-01, 02, 03, 04). Run from repo root. Total time: under 5 minutes.

## Prerequisites

- Collector installed: `pip install -e .`
- Optional: API + dashboard for full event view (see [SERVER.md](SERVER.md))

## 1. One-shot scan with verbose (see detection and summary)

```bash
detec-agent --dry-run --verbose
```

When behavioral patterns fire, the CLI shows the canonical detection name (DETEC-BEH-CORE-01, 02, 03, or 04) in evidence and summary:

- `DETECTED: Unknown Agent` and confidence
- `action_summary` with the analyst sentence (e.g. "Autonomous shell execution pattern detected: N shell children spawned from a model-linked parent process over W seconds.")
- Evidence ref: `evidence://collector-scan/Unknown Agent/...`; event payload includes `detection_codes`: `["DETEC-BEH-CORE-01"]`, etc.

## 2. Why each detection matters (buyer-facing)

One line per detection in security-outcome language:

- **DETEC-BEH-CORE-01 (Autonomous shell fan-out):** Detects autonomous command execution that looks like an agent operating beyond normal interactive developer behavior.
- **DETEC-BEH-CORE-02 (Agentic read-modify-write loop):** Detects AI-assisted code modification loops, not just AI tool presence.
- **DETEC-BEH-CORE-03 (Sensitive access + outbound):** Detects high-risk sequences where sensitive material is accessed and followed by outbound model or network activity.
- **DETEC-BEH-CORE-04 (Agent execution chain):** Detects the full agent loop: model call, then shell/command execution, then file or git activity, in order within a time window.

## 3. What each detection demonstrates

### DETEC-BEH-CORE-03: Sensitive access followed by outbound

- **What to show:** A process reads a sensitive path (e.g. `.env`, `.aws/credentials`) and then makes outbound connections (model API or unknown host).
- **Why EDR misses it:** EDR sees file access and network separately. Detec correlates same process tree and enforces temporal ordering (access then outbound within a window) and classifies destination (model vs unknown).

### DETEC-BEH-CORE-02: Read-modify-write loop

- **What to show:** Interleaved file edits and model API (or local inference) calls in short cycles from one process tree.
- **Why EDR misses it:** EDR does not correlate file and network by cadence to infer "file, then model call, then file again" as an agentic coding loop. Detec uses a timeline and cycle window to detect this pattern.

### DETEC-BEH-CORE-01: Autonomous shell fan-out

- **What to show:** Many shell children spawned from a parent process that also has LLM activity (model-linked).
- **Why EDR misses it:** EDR sees generic shell execution. Detec counts shells in a time window and ties the tree to LLM activity so "agent session" is explicit.

### DETEC-BEH-CORE-04: Agent execution chain

- **What to show:** LLM API call, then shell or interpreter execution, then file write or git add/commit, in that order within a configurable window (same process tree).
- **Why EDR misses it:** EDR does not correlate network, process, and file by strict temporal order across layers. Detec requires t_llm <= t_shell <= t_file and uses one process tree so the "model then command then artifact" chain is explicit.

## 4. Canonical event examples

One minimal example per detection. Security people trust examples.

### DETEC-BEH-CORE-01 (autonomous shell fan-out)

```json
{
  "event_type": "detection.observed",
  "event_version": "0.4.0",
  "tool": {
    "name": "Unknown Agent",
    "attribution_confidence": 0.52,
    "attribution_sources": ["process", "behavior"]
  },
  "action": {
    "type": "exec",
    "risk_class": "R3",
    "summary": "Autonomous shell execution pattern detected: 8 shell children spawned from a model-linked parent process over 42 seconds.",
    "raw_ref": "evidence://collector-scan/Unknown%20Agent/sess-01"
  },
  "policy": {
    "decision_state": "warn",
    "rule_id": "ENFORCE-002",
    "reason_codes": ["medium_confidence", "class_c_tool", "action_risk_r3"]
  }
}
```

### DETEC-BEH-CORE-02 (read-modify-write loop)

```json
{
  "event_type": "detection.observed",
  "event_version": "0.4.0",
  "tool": {
    "name": "Unknown Agent",
    "attribution_confidence": 0.58,
    "attribution_sources": ["file", "network", "behavior"]
  },
  "action": {
    "type": "write",
    "risk_class": "R2",
    "summary": "Agentic read-modify-write loop detected: 4 file-model cycles in 10 seconds affecting /proj/src, /proj/lib, tied to process cursor (api.anthropic.com:443).",
    "raw_ref": "evidence://collector-scan/Unknown%20Agent/sess-02"
  },
  "policy": {
    "decision_state": "warn",
    "rule_id": "ENFORCE-002",
    "reason_codes": ["medium_confidence", "class_c_tool"]
  }
}
```

### DETEC-BEH-CORE-03 (sensitive access + outbound)

```json
{
  "event_type": "detection.observed",
  "event_version": "0.4.0",
  "tool": {
    "name": "Unknown Agent",
    "attribution_confidence": 0.61,
    "attribution_sources": ["file", "network", "identity"]
  },
  "action": {
    "type": "exec",
    "risk_class": "R3",
    "summary": "Sensitive access followed by outbound activity: /home/dev/.env accessed; outbound connections to api.anthropic.com:443 within 12 seconds; destination type model.",
    "raw_ref": "evidence://collector-scan/Unknown%20Agent/sess-03"
  },
  "policy": {
    "decision_state": "approval_required",
    "rule_id": "ENFORCE-003",
    "reason_codes": ["medium_confidence", "class_c_tool", "sensitive_asset", "action_risk_r3"]
  }
}
```

### DETEC-BEH-CORE-04 (agent execution chain)

```json
{
  "event_type": "detection.observed",
  "event_version": "0.4.0",
  "tool": {
    "name": "Unknown Agent",
    "attribution_confidence": 0.52,
    "attribution_sources": ["network", "process", "file", "behavior"]
  },
  "action": {
    "type": "exec",
    "risk_class": "R2",
    "summary": "AI-driven command execution chain detected: LLM API call: api.anthropic.com:443; shell execution: bash; file write detected in 10.0 seconds.",
    "raw_ref": "evidence://collector-scan/Unknown%20Agent/sess-04"
  },
  "policy": {
    "decision_state": "warn",
    "rule_id": "ENFORCE-002",
    "reason_codes": ["medium_confidence", "class_c_tool"]
  }
}
```

Full event schema and optional fields (e.g. `evidence.detection_codes` when evidence is inlined): [schemas/canonical-event-schema.json](../schemas/canonical-event-schema.json). Policy mapping: [behavioral-core-policy-mapping.md](behavioral-core-policy-mapping.md).

## 5. Replay tests as demo evidence

To prove the core detections fire on known scenarios:

```bash
pytest collector/tests/test_behavioral_core_detections.py -v
```

This runs event-level fixtures for DETEC-BEH-CORE-01, 02, and 03 (positive, false-positive, ambiguous). DETEC-BEH-CORE-04 is covered by `test_behavioral_scanner.py` (TestBEH009AgentExecutionChain and the full-scanner detection_code test):

```bash
pytest collector/tests/test_behavioral_scanner.py::TestBEH009AgentExecutionChain -v
pytest collector/tests/test_behavioral_scanner.py -k "beh009 or detection_code" -v
```

Use these in demos to show "we assert detection and evidence shape for each core behavior." All behavioral, calibration, enforcement e2e, and confidence tests pass; that proves the detections are tested, the confidence model is calibrated, the policy layer is connected, and the system is not ad hoc heuristics.

## 6. Specs and config

- Detection specs: [project-specs/detec-beh-core-01-spec.md](../project-specs/detec-beh-core-01-spec.md), [detec-beh-core-02-spec.md](../project-specs/detec-beh-core-02-spec.md), [detec-beh-core-03-spec.md](../project-specs/detec-beh-core-03-spec.md).
- Thresholds: [collector/config/behavioral.json](../collector/config/behavioral.json) (pattern config for DETEC-BEH-CORE-01/02/03/04).

## 7. Polished demo artifacts (60 seconds each)

One demo per core detection with command, detection output, evidence summary, and policy result:

| Detection | Artifact |
|-----------|----------|
| DETEC-BEH-CORE-01 | [docs/demo-proof/DETEC-BEH-CORE-01-demo.md](demo-proof/DETEC-BEH-CORE-01-demo.md) |
| DETEC-BEH-CORE-02 | [docs/demo-proof/DETEC-BEH-CORE-02-demo.md](demo-proof/DETEC-BEH-CORE-02-demo.md) |
| DETEC-BEH-CORE-03 | [docs/demo-proof/DETEC-BEH-CORE-03-demo.md](demo-proof/DETEC-BEH-CORE-03-demo.md) |
| DETEC-BEH-CORE-04 | [docs/demo-proof/DETEC-BEH-CORE-04-demo.md](demo-proof/DETEC-BEH-CORE-04-demo.md) |
