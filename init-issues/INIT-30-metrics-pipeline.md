# INIT-30 — Metrics Pipeline (Full Deep Revision)

## Scope
Issue: **INIT-30**
Objective: define a metrics pipeline that measures detection quality, governance effectiveness, and operational reliability with enough rigor to support engineering decisions and buyer credibility.

The pipeline must be:
- reproducible,
- explainable,
- resilient to noisy telemetry,
- and directly tied to policy outcomes.

---

## 1) Why Metrics Pipeline Is a Core Product Component
Without strong metrics, teams cannot distinguish:
- real detection improvements vs. anecdotal wins,
- safe enforcement vs. user-friction regressions,
- robust confidence scoring vs. unstable heuristics.

For this product, metrics are not reporting garnish—they are control-system feedback.

---

## 2) Metric Domains

### A) Detection Quality Metrics
- **Precision**: % detections that are truly correct.
- **Recall**: % true events that were detected.
- **False Positive Rate** by tool/class/context.
- **False Negative Rate** by scenario category.
- **Coverage Completeness**: proportion of matrix cells with valid observations.

### B) Confidence Quality Metrics
- **Calibration**: whether high scores correspond to higher true correctness.
- **Confidence Drift**: score movement for same scenario across versions.
- **Band Stability**: consistency of low/medium/high assignments.

### C) Enforcement Metrics
- **Decision Accuracy** vs expected policy outcomes.
- **Escalation Correctness** (Detect→Warn→Approval→Block behavior).
- **Approval Path Utilization** and outcomes.
- **Block Validity Rate** (confirmed justified blocks vs overblocks).

### D) Operational Metrics
- **Time to Detect (TTD)**
- **Time to Decision (TTDec)**
- **Event Processing Latency**
- **Evidence Completion Rate**
- **Pipeline Error Rate** and retry behavior.

### E) Trust / Governance Metrics
- **Exception Reliance Rate** (how often policy needs bypass)
- **Stale Exception Ratio**
- **Repeat Violation Escalation Success**
- **Analyst Override Frequency**

---

## 3) Data Model for Metrics Events
Minimum normalized record fields:
- `run_id`
- `scenario_id`
- `matrix_cell_id`
- `tool_id` + `tool_class`
- `environment_id` (OS, deployment mode, topology)
- `asset_sensitivity_tier`
- `action_risk_class`
- `expected_decision`
- `observed_decision`
- `expected_confidence_band`
- `observed_confidence_score`
- `outcome_label` (TP/FP/TN/FN for detection-specific slices)
- `latency_ms` (detect/decision/evidence)
- `evidence_complete` (bool)
- `rule_id` / `rule_version`
- `timestamp`

This schema enables unified analytics across detection, policy, and operational dimensions.

---

## 4) Measurement Semantics (Important)

### Precision/Recall calculation boundaries
- define what counts as a “positive” per tool class and scenario type.
- maintain separate confusion matrices for:
  - tool attribution,
  - action-risk classification,
  - policy decision correctness.

### Confidence calibration
- use reliability curves by tool class and scenario type.
- track expected vs empirical correctness at each confidence band.

### Decision accuracy
- compare observed decision to expected rule outcome from matrix/replay definitions.
- classify mismatches by root cause (rule, signal loss, scoring drift, implementation bug).

---

## 5) Pipeline Stages

### Stage 1: Ingest
- collect raw replay/production-like event outputs.
- validate required fields and schema versions.

### Stage 2: Normalize
- map provider/tool-specific fields into canonical schema.
- attach context dimensions (class, sensitivity, risk tier).

### Stage 3: Evaluate
- compute derived metrics and confusion matrices.
- run calibration and drift analyses.

### Stage 4: Aggregate
- roll up by tool, class, OS, topology, sensitivity tier.
- produce release-level and trend-level views.

### Stage 5: Publish
- internal engineering dashboard,
- security/analyst dashboard,
- buyer-safe benchmark extracts.

---

## 6) Segmentation Requirements
Every core metric must be sliceable by:
- tool and tool class,
- OS and deployment mode,
- network topology,
- sensitivity tier,
- action risk class,
- confidence band,
- release version.

Without segmentation, aggregate metrics can hide critical regressions.

---

## 7) Thresholds and Gates
Define release gates such as:
- precision floor for Class C in Tier2/3 contexts,
- max tolerated decision-mismatch rate,
- max allowed confidence drift for stable scenarios,
- minimum evidence completion rate,
- max overblock rate in baseline scenarios.

Gates should be versioned and tuned with explicit change control.

---

## 8) Drift Detection
Track drift over time for:
- confidence scores on fixed scenarios,
- precision/recall trends,
- policy decision distribution shifts,
- latency regressions.

Drift categories:
- benign drift (expected after rule change),
- suspicious drift (unexplained),
- critical drift (release-blocking).

---

## 9) Failure Modes and Safeguards

### Failure Mode: Good aggregate metrics hide critical segment regressions
Safeguard:
- enforce segment-level gates for high-risk slices.

### Failure Mode: Metric gaming via easy scenarios
Safeguard:
- weighted scoring prioritizing high-risk/high-sensitivity cells.

### Failure Mode: Incomplete evidence still counted as pass
Safeguard:
- evidence completeness is mandatory quality gate.

### Failure Mode: Schema drift breaks longitudinal comparability
Safeguard:
- strict schema versioning + compatibility adapters + backfill policy.

### Failure Mode: False confidence from sparse data
Safeguard:
- confidence intervals and minimum sample requirements per metric view.

---

## 10) Dashboard and Reporting Requirements

### Engineering dashboard
- precision/recall by tool/class
- confidence calibration and drift
- failure root-cause breakdown
- release gate status

### Security operations dashboard
- decision accuracy by sensitivity tier
- escalation funnel health
- exception usage and override patterns

### Buyer-facing summary
- coverage + key quality metrics
- known gaps and mitigation trajectory
- clear caveats on unvalidated segments

---

## 11) Validation Plan

### Functional validation
1. schema conformance and ingestion integrity.
2. deterministic recompute of metrics from same source dataset.
3. segmentation consistency across dashboards.

### Analytical validation
1. precision/recall sanity checks on labeled runs.
2. calibration curve consistency checks.
3. drift alert correctness.

### Operational validation
1. end-to-end metric generation within acceptable latency.
2. release gate behavior under simulated regressions.

Required artifacts:
- metric dictionary,
- gate threshold config,
- sample dashboard exports,
- drift report examples.

---

## 12) Buyer-Credibility Statement
"We measure not just detection volume, but detection correctness, confidence calibration, and policy decision quality across risk and sensitivity contexts. Our metrics pipeline is built for transparent, reproducible security outcomes."

---

## 13) Acceptance Checklist
- [x] Metric domains and definitions specified.
- [x] Data model and pipeline stages documented.
- [x] Segmentation, thresholds, and gating requirements defined.
- [x] Drift and failure-mode safeguards captured.
- [x] Dashboard/reporting and validation requirements specified.
- [ ] Empirical metrics run evidence attached.
