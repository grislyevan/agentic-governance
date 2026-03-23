# INIT-29 — Automated Replay Scenarios (Full Deep Revision)

## Scope
Issue: **INIT-29**
Objective: define a robust, deterministic replay framework that exercises detection and governance controls across normal, risky, and adversarial AI-tool workflows.

Automated replay is the mechanism that turns one-time testing into repeatable assurance.

---

## 1) Why Replay Matters
Without replay automation, teams rely on ad hoc manual tests that are:
- non-repeatable,
- hard to compare over releases,
- vulnerable to selective demonstration bias.

Replay scenarios provide:
- regression protection,
- policy stability validation,
- confidence calibration over time,
- benchmark credibility with traceable evidence.

---

## 2) Replay Architecture Overview

### Core components
1. **Scenario definition layer**
   - declarative scenario specs (inputs, actions, expected outputs).
2. **Execution harness**
   - drives tool workflows in controlled environments.
3. **Observation collectors**
   - capture process/file/network/identity/behavior telemetry.
4. **Policy assertion engine**
   - compares observed decisions to expected outcomes.
5. **Evidence packager**
   - bundles artifacts, hashes, and run metadata.

### Key property
- same scenario + same environment + same version should produce comparable outcomes within defined tolerance.

---

## 3) Scenario Taxonomy

### A) Baseline / Positive
Purpose: verify expected, policy-compliant behavior.
Examples:
- approved tool usage in non-sensitive repo,
- normal assistive coding loop,
- local runtime with sanctioned model set.

### B) Risky but Legitimate
Purpose: test escalation and approval behavior.
Examples:
- broad but approved refactor,
- sensitive path access with valid approval token,
- sanctioned egress in bounded scope.

### C) Adversarial / Evasion
Purpose: test resilience against bypass tactics.
Examples:
- renamed binary/wrapper execution,
- proxy/shared-backend attribution ambiguity,
- containerized execution with reduced visibility,
- config drift toward unsanctioned targets.

### D) Failure-Mode / Partial Telemetry
Purpose: validate safe behavior when observability degrades.
Examples:
- missing process lineage,
- delayed identity enrichment,
- partial netflow loss.

---

## 4) Scenario Definition Schema (Minimum)
Each scenario must define:
- `scenario_id`
- `matrix_cell_id` (link to INIT-28)
- `scenario_type`
- `preconditions`
- `action_sequence[]`
- `expected_signals_by_layer`
- `expected_confidence_band`
- `expected_policy_decision`
- `expected_reason_codes`
- `required_evidence_types[]`
- `tolerance_rules`

Optional but recommended:
- `risk_hypothesis`
- `known_blind_spots`
- `cleanup_procedure`

---

## 5) Execution Semantics

### Pre-run phase
- provision environment snapshot,
- validate tool/version prerequisites,
- seed deterministic inputs,
- verify collectors are healthy.

### Run phase
- execute action sequence with timestamped checkpoints,
- capture telemetry continuously,
- emit intermediate state markers.

### Post-run phase
- assert expected decision path,
- evaluate confidence deviation vs tolerance,
- package evidence and integrity hashes,
- run cleanup and reset environment.

---

## 6) Determinism and Variance Control

Determinism controls:
- fixed scenario scripts and input fixtures,
- stable environment images where possible,
- seeded randomness for stochastic paths,
- pinned tool/runtime versions in replay manifests.

Variance policy:
- allow bounded variance in timing,
- disallow unexplained confidence/decision swings,
- classify variance as acceptable, suspicious, or fail.

---

## 7) Assertion Model
Each scenario must assert:
1. **Signal assertions**
   - required telemetry layer observations present.
2. **Confidence assertions**
   - score falls in expected band.
3. **Decision assertions**
   - ladder outcome matches expected state.
4. **Explainability assertions**
   - reason codes and evidence references complete.
5. **Integrity assertions**
   - artifact hashes and linkage are valid.

---

## 8) Failure Classification
When replay fails, categorize by root class:
- `SIGNAL_MISSING`
- `CONFIDENCE_DRIFT`
- `DECISION_MISMATCH`
- `EXPLAINABILITY_INCOMPLETE`
- `EVIDENCE_INTEGRITY_FAIL`
- `HARNESS_RUNTIME_FAIL`

Each failure must emit remediation guidance and owner assignment.

---

## 9) Coverage Strategy for Replay Library

### Minimum per tool
- 3 baseline positives,
- 2 evasions/failures,
- 1 high-sensitivity governance scenario.

### Priority sequencing
1. Class C tools first (highest impact)
2. sensitivity Tier2/Tier3 cells
3. R3/R4 action classes

### Expansion policy
- add new scenarios whenever a real customer incident or bug reveals a missing pattern.

---

## 10) Evidence Packaging Requirements
Every run must produce:
- run manifest (versions, environment, scenario metadata),
- event timeline export,
- decision trace,
- collected evidence object references,
- pass/fail report,
- residual risk note (if conditional pass).

All artifacts should be hash-linked and retrievable by run ID.

---

## 11) CI/CD and Release Gating Integration
Replay suite should be tiered:
- **Smoke tier**: critical scenarios every build.
- **Standard tier**: broader set per release candidate.
- **Deep tier**: full matrix sweep on cadence.

Release gates should block promotion when:
- critical scenario fails,
- decision mismatch rate exceeds threshold,
- confidence drift exceeds tolerance without approved exception.

---

## 12) Failure Modes and Safeguards

### Failure Mode: Replay scripts drift from real-world behavior
Safeguard:
- periodic scenario realism review using production-like telemetry patterns.

### Failure Mode: Harness hides policy regressions
Safeguard:
- independent assertion checks and random audit of pass results.

### Failure Mode: Overfitting to known scenarios
Safeguard:
- rotating unseen challenge scenarios and adversarial injections.

### Failure Mode: Evidence gaps despite pass status
Safeguard:
- pass requires evidence completeness check, not just decision match.

---

## 13) Validation Plan for This Spec
1. implement pilot replay set for one Class A, one B, one C tool.
2. verify schema completeness and deterministic rerun behavior.
3. measure drift over repeated executions.
4. produce first replay coverage dashboard.

Required outputs:
- replay schema validation report,
- scenario pass/fail summary,
- confidence drift chart,
- unresolved-gaps list.

---

## 14) Buyer-Credibility Statement
"We continuously replay realistic and adversarial AI-tool scenarios in a deterministic harness. This catches regressions early, quantifies drift, and ensures policy decisions remain evidence-backed over time."

---

## 15) Acceptance Checklist
- [x] Replay architecture and taxonomy defined.
- [x] Scenario schema and execution semantics specified.
- [x] Assertion model and failure taxonomy documented.
- [x] Evidence packaging and release gating requirements defined.
- [x] Failure modes and safeguards captured.
- [ ] Empirical replay run evidence attached.
