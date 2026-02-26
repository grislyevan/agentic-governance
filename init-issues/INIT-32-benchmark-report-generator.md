# INIT-32 — Benchmark Report Generator (Full Deep Revision)

## Scope
Issue: **INIT-32**
Objective: define a benchmark report generator that transforms validation outputs into consistent, defensible, and audience-appropriate reports for engineering, security, and buyer stakeholders.

The generator must produce reports that are:
- traceable to underlying evidence,
- reproducible across releases,
- transparent about limitations,
- and safe to share externally when sanitized.

---

## 1) Why Report Generation Needs Product-Grade Design
Manual report assembly introduces risk:
- inconsistent definitions,
- omitted caveats,
- cherry-picked results,
- broken evidence traceability,
- difficult comparison across versions.

A structured generator enforces narrative integrity and keeps claims aligned with measured outcomes.

---

## 2) Report Output Types

### A) Internal Technical Report
Audience: detection engineering, security architecture, operations.
Purpose:
- full-fidelity diagnostics,
- regression and drift analysis,
- failure root-cause prioritization.

Includes:
- complete metric slices,
- scenario-level failures,
- evidence references,
- unresolved gaps and risk register.

### B) Internal Executive Summary
Audience: leadership/product/Go-to-market.
Purpose:
- high-level posture,
- release readiness,
- top risks and mitigations.

Includes:
- key KPIs,
- trend summary,
- gate pass/fail status,
- remediation ownership highlights.

### C) External Buyer-Safe Report
Audience: prospects/customers/security evaluators.
Purpose:
- capability transparency,
- trust-building via measurable outcomes,
- clear articulation of known limitations.

Includes:
- coverage overview,
- validated strengths,
- known gaps + mitigation trajectory,
- sanitized evidence snippets.

---

## 3) Core Input Data Contracts
Generator consumes canonical outputs from:
- test matrix (INIT-28),
- replay scenarios (INIT-29),
- metrics pipeline (INIT-30),
- evasion suite (INIT-31),
- audit/decision logs (INIT-26/24).

Minimum input entities:
- run manifests,
- scenario outcomes,
- confidence/decision metrics,
- pass/fail and failure taxonomy,
- evidence index with integrity metadata,
- unresolved risk and mitigation backlog.

---

## 4) Report Data Model
Each report build should include:
- `report_id`
- `report_type`
- `build_timestamp`
- `source_release_version`
- `input_run_set_ids[]`
- `coverage_snapshot`
- `metric_snapshot`
- `decision_quality_snapshot`
- `evasion_resilience_snapshot`
- `known_gaps[]`
- `mitigation_plan[]`
- `evidence_manifest_id`
- `sanitization_profile` (internal/external)

This model enables reproducibility and audit trail.

---

## 5) Section Blueprint (Canonical)

### 1. Executive Summary
- overall posture,
- release gate status,
- material changes since previous report.

### 2. Coverage & Methodology
- matrix dimensions tested,
- scenario distribution,
- excluded/uncovered cells.

### 3. Detection Quality
- precision/recall views,
- confidence calibration highlights,
- class/tool breakdown.

### 4. Governance Quality
- enforcement decision correctness,
- escalation funnel behavior,
- approval/exception usage patterns.

### 5. Evasion Resilience
- evasion categories tested,
- R0-R3 degradation outcomes,
- unresolved R2/R3 issues.

### 6. Known Gaps and Limitations
- explicit limitation statements,
- impact severity,
- mitigation status and target dates.

### 7. Evidence Index
- linked evidence references,
- integrity status,
- retrieval controls.

### 8. Action Plan
- prioritized remediation backlog,
- owners and timelines,
- release impact assessment.

---

## 6) Sanitization and Audience Controls

### Internal mode
- full detail, internal identifiers, complete evidence linkage.

### External mode
- redacted internal host/user identifiers,
- no sensitive path exposure,
- aggregate metrics where needed,
- only shareable evidence excerpts.

Sanitization must preserve truthfulness:
- do not hide known limitations,
- do not inflate confidence claims,
- clearly label unvalidated areas.

---

## 7) Claim Integrity Rules
Every externally material claim must be:
1. backed by metrics from current report scope,
2. linked to evidence or method section,
3. bounded by caveats where appropriate.

Disallowed behaviors:
- implying complete coverage when cells are missing,
- omitting critical unresolved evasion failures,
- mixing metrics from incompatible run sets without disclosure.

---

## 8) Comparative Trend Reporting
Generator should support prior-version diffing:
- quality improvement/regression by class,
- confidence drift highlights,
- gate status deltas,
- risk backlog movement.

Trend sections should distinguish:
- statistically meaningful movement,
- noise-level fluctuations.

---

## 9) Failure Modes and Safeguards

### Failure Mode: Report says “pass” while critical slices failed
Safeguard:
- hard fail flag if any critical gate fails.

### Failure Mode: Missing caveats in buyer report
Safeguard:
- mandatory limitations section validation.

### Failure Mode: Broken evidence links
Safeguard:
- pre-publish evidence integrity check.

### Failure Mode: Inconsistent definitions across reports
Safeguard:
- metric dictionary and schema version pinning included in report metadata.

### Failure Mode: Manual tampering of narrative
Safeguard:
- generated sections signed with build metadata and source manifest hash.

---

## 10) Publishing Workflow
1. collect validated input run set.
2. run schema and integrity checks.
3. generate internal technical report.
4. derive executive summary.
5. generate external sanitized variant.
6. run claim integrity linter.
7. publish with immutable report metadata.

Approvals:
- engineering owner sign-off,
- security owner sign-off for external report.

---

## 11) Validation Plan

### Functional validation
- same input set generates stable report outputs.
- report sections populated and ordered per blueprint.

### Integrity validation
- all claims map to source metrics/evidence.
- evidence references resolve and pass hash checks.

### Audience validation
- external report passes sanitization checks.
- internal report preserves required diagnostic detail.

Required artifacts:
- sample internal + external report pair,
- claim integrity check output,
- evidence-link validation output.

---

## 12) Buyer-Credibility Statement
"Our benchmark reports are generated from versioned, replay-backed data with explicit evidence linkage and transparent limitations. This prevents demo-driven overclaiming and supports repeatable trust in detection and governance quality."

---

## 13) Acceptance Checklist
- [x] Output report types and audience modes defined.
- [x] Input contracts and report data model specified.
- [x] Canonical section blueprint documented.
- [x] Sanitization and claim integrity rules defined.
- [x] Failure-mode safeguards and publishing workflow documented.
- [x] Validation requirements and artifacts specified.
- [ ] Empirical generated report evidence attached.
