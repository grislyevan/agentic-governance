# Detec Core Behavioral Detection Sprint — Project Specification

## Project name

detec-beh-core

## Goal

Build a focused project that proves Detec can detect high-value AI-agent behavior that traditional EDR and simple signature-based AI tool detection will miss.

## Outcome

At the end of this project, Detec should reliably detect and explain three security-relevant behaviors:

1. **DETEC-BEH-CORE-01** — Autonomous shell fan-out from an AI agent session
2. **DETEC-BEH-CORE-02** — Agentic read-modify-write coding loop tied to LLM activity
3. **DETEC-BEH-CORE-03** — Credential or sensitive config access followed by outbound model/network activity

These detections must work for both known tools (Claude Code, Cursor, Open Interpreter, etc.) and unknown/renamed agentic workflows.

## Scope

### In scope

- Tighten and productionize the three detections
- Define thresholds and confidence behavior
- Produce demo-ready evidence output
- Create test scenarios and replay fixtures
- Generate policy mappings for each detection

### Out of scope

- Major dashboard work
- Generalized management console expansion
- Broad marketplace integrations
- Polished enterprise workflow UX

## Success metrics

### Detection quality

- True positives across lab scenarios
- False positive rate in normal dev sessions
- Confidence stability across replay fixtures

### Product value

- Can a security engineer understand why it fired?
- Does it justify a policy decision?
- Does it demonstrate something EDR or simple tool signatures miss?

### Demo readiness

- Can each detection be shown in under 90 seconds?
- Does the CLI/event output look credible?
- Does the evidence look actionable?

## Deliverables

1. **Detection specs** — One-page implementation spec per detection (intent, telemetry, thresholds, penalties, evidence, sample output, expected false positives).
2. **Replay fixtures** — Positive, ambiguous, false-positive guardrail, and renamed/unknown agent scenario per detection.
3. **Tests** — Positive detection, threshold edge cases, confidence band expectations, no-fire for common dev behavior.
4. **Analyst-facing evidence summaries** — One-sentence human-readable summary per detection in event output.
5. **Policy mapping** — Map each detection to default actions (warn / approval_required / block) and document.
6. **Demo pack** — Single demo sequence for all three detections with CLI output, emitted events, policy decision, and short analyst explanation.

## Implementation order

1. DETEC-BEH-CORE-03 (sensitive access + outbound) — strongest buyer story
2. DETEC-BEH-CORE-02 (read-modify-write loop) — core AI coding visibility
3. DETEC-BEH-CORE-01 (autonomous shell fan-out) — autonomous execution depth

## Strategic framing

This project proves that Detec can detect AI-agent behaviors that other endpoint and AI governance tools cannot explain or govern. It is not framed as "more detections" or "another dashboard feature."
