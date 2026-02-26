# INIT-28 — Test Matrix Definition (Full Deep Revision)

## Scope
Issue: **INIT-28**
Objective: define a repeatable, decision-useful test matrix that validates AI-tool detection and governance quality across realistic enterprise conditions.

This matrix is the foundation for:
- engineering validation,
- release gating,
- benchmark credibility,
- buyer proof.

---

## 1) Why the Matrix Matters
Without a formal matrix, testing drifts toward ad hoc demos and cherry-picked scenarios.

A proper matrix ensures:
- coverage is deliberate,
- gaps are visible,
- results are comparable over time,
- claims remain evidence-backed.

---

## 2) Matrix Axes (Canonical)

### A) Tool Axis
- all in-scope tools (INIT coverage set)
- include class mapping (A/B/C)
- include version/build metadata

### B) Platform Axis
- OS family: macOS / Windows / Linux
- optional: architecture variants if behavior differs
- endpoint posture: managed vs unmanaged baseline

### C) Deployment Context Axis
- native host execution
- container/devcontainer execution
- remote/dev workspace patterns (where applicable)

### D) Network Topology Axis
- direct internet egress
- corporate proxy
- shared model gateway
- mostly-localhost inference paths

### E) Asset Sensitivity Axis
- Tier0: non-sensitive sandbox
- Tier1: business-sensitive repo
- Tier2: high-value engineering assets
- Tier3: restricted/regulatory/crown-jewel scope

### F) Action Risk Axis
- R1 read/low impact
- R2 scoped writes
- R3 broad writes/egress
- R4 privileged/prohibited patterns

---

## 3) Test Cell Definition
Each matrix cell is a tuple:
`{tool, os, deployment_context, network_topology, sensitivity_tier, action_risk}`

Each cell must define:
1. expected detection signals (by layer),
2. expected confidence band,
3. expected policy decision state,
4. expected evidence outputs,
5. pass/fail criteria.

---

## 4) Coverage Strategy

### Minimum baseline coverage (release gate)
- every tool must have:
  - >=1 cell per major OS OR justified omission,
  - >=1 normal-use scenario,
  - >=1 evasion/failure scenario,
  - >=1 sensitive-scope governance scenario.

### Priority weighting
- prioritize Class C + higher sensitivity + higher action risk for early depth.
- include representative Class A/B cells for policy completeness.

### Gap handling
- uncovered cells must be tracked with explicit risk statements and planned mitigation dates.

---

## 5) Scenario Types Required Per Tool

### A) Positive/Baseline Scenarios
- expected/approved behavior,
- should produce stable confidence and policy outputs.

### B) Evasion/Adversarial Scenarios
- renamed wrappers,
- partial telemetry contexts,
- proxy/shared-backend ambiguity,
- containerization visibility degradation.

### C) Governance Stress Scenarios
- risky action near policy boundary,
- repeated warning escalation,
- approval and exception interaction.

### D) Failure-Mode Scenarios
- missing telemetry stream,
- identity uncertainty,
- conflicting policy conditions.

---

## 6) Expected Outputs Per Run
Each test run linked to matrix cell must emit:
- run ID,
- environment metadata,
- scenario ID,
- signal-layer observations,
- confidence result and rationale,
- policy decision and rule trace,
- evidence references,
- residual risk notes,
- pass/fail + failure reason category.

---

## 7) Pass/Fail Criteria Model

### Pass
- expected minimum signals observed,
- confidence within expected band,
- policy action matches expected outcome,
- evidence completeness meets schema requirements.

### Conditional Pass
- partial telemetry but conservative decision behavior correct,
- residual risk explicitly recorded.

### Fail
- missed required signal set,
- incorrect confidence/decision,
- missing evidence linkage,
- non-deterministic decision behavior under same inputs.

---

## 8) Determinism and Reproducibility Requirements
- scenario definitions are versioned,
- environment provisioning is documented,
- random seeds/config knobs are fixed where applicable,
- reruns of same scenario should remain within tolerance.

Tolerance policies must define acceptable variance for:
- timing metrics,
- confidence score deltas,
- decision stability.

---

## 9) Matrix Data Model Requirements
Minimum matrix metadata fields:
- `matrix_cell_id`
- `tool_id`
- `tool_class`
- `os`
- `deployment_context`
- `network_topology`
- `sensitivity_tier`
- `action_risk`
- `scenario_type`
- `expected_confidence_band`
- `expected_decision`
- `required_evidence_types[]`
- `priority`
- `status`

This model should integrate directly with validation and reporting pipelines.

---

## 10) Reporting Requirements
The matrix must support reporting views for:
- coverage heatmap by tool/class,
- fail concentration by axis,
- high-risk uncovered cells,
- trend over release versions,
- confidence calibration drift.

Buyer-facing output should show:
- transparent coverage,
- known gaps,
- mitigation roadmap.

---

## 11) Failure Modes and Mitigations

### Failure Mode: Coverage illusion (many easy tests, few hard tests)
Mitigation:
- weighted coverage metrics prioritizing high-risk cells.

### Failure Mode: Non-comparable run outputs
Mitigation:
- strict run schema + deterministic scenario IDs.

### Failure Mode: Silent uncovered high-risk contexts
Mitigation:
- mandatory uncovered-cell report for each release.

### Failure Mode: Benchmark overfitting
Mitigation:
- rotate adversarial scenarios and include unseen challenge cells.

---

## 12) Validation Plan for This Matrix Specification
1. Dry-run matrix population for all tools and classes.
2. Confirm every cell has expected signal/decision/evidence definitions.
3. Execute representative subset and verify output schema completeness.
4. Generate first coverage heatmap and gap report.

Required artifacts:
- matrix definition file,
- runbook mapping scenario IDs to cells,
- initial coverage report.

---

## 13) Buyer-Credibility Statement
"Our benchmark is built on a structured matrix across tool, platform, context, risk, and sensitivity dimensions. We report both coverage and gaps, so claims are evidence-based and reproducible rather than demo-driven."

---

## 14) Acceptance Checklist
- [x] Matrix axes and cell model fully defined.
- [x] Coverage strategy and prioritization documented.
- [x] Pass/fail and reproducibility criteria specified.
- [x] Data model and reporting requirements defined.
- [x] Failure modes and mitigations captured.
- [ ] Empirical matrix execution evidence attached.
