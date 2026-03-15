# Detec Signal Credibility — Task List

Source: [project-specs/detec-signal-credibility-setup.md](../project-specs/detec-signal-credibility-setup.md)

## Quoted requirements from spec

- **Goal:** "Improve the credibility of Detec scan results by reducing noisy, weak, or confusing detections so the output feels more intentional and trustworthy to security-minded users."
- **Requirements (excerpt):** "Identify scan outputs that are technically valid but weak, noisy, misleading, or trust-reducing. Focus especially on cases where: 'no real signals detected' still results in a full detection event; confidence is extremely low; only generic environment/API-key evidence exists; extension-host or shared-process evidence creates ambiguous attribution. Improve credibility using minimal, targeted changes. Preserve truthful reporting. If thresholds, gating, or wording are changed, they must be justified and tested. Maintain the current clean schema-valid output."
- **Success criteria:** "Normal scan output feels more credible to a technical reviewer. Extremely weak or confusing detections are reduced, reclassified, or clarified. Strong detections still appear correctly. Schema-valid output remains intact. Changes are minimal, justified, and tested."
- **Deliverables:** "Updated task list at project-tasks/detec-signal-credibility-tasklist.md; Foundation/architecture guidance for credibility improvements; Implementation changes for targeted weak-signal handling; QA evidence with before/after examples; Completion report with final status and remaining limitations."
- **Out of scope:** "Dashboard features; packaging/release work; landing-page work; broad repo cleanup; major scoring-engine rewrite."

---

## Tasks

### Task 1: Create spec and task list (pre-step)

- **What:** Ensure the project spec exists at `project-specs/detec-signal-credibility-setup.md` and this task list at `project-tasks/detec-signal-credibility-tasklist.md` with quoted requirements and acceptance criteria.
- **Acceptance criteria:**
  - [x] `project-specs/detec-signal-credibility-setup.md` exists and contains goal, requirements, success criteria, and out of scope.
  - [x] `project-tasks/detec-signal-credibility-tasklist.md` exists with quoted spec requirements and tasks below.
- **Status:** [x]

---

### Task 2: Add foundation/architecture doc for credibility

- **What:** Add a project-docs document that describes the emission path (orchestrator to _process_detection to build_event to emit), where credibility interventions fit, credibility levers (emission gating, attribution thresholds, wording), and constraints (schema-valid output, do not hide real findings, calibration tests pass).
- **Acceptance criteria:**
  - [x] `project-docs/detec-signal-credibility-architecture.md` exists.
  - [x] Doc describes current emission path and credibility levers (emission gating, optional attribution thresholds, wording).
  - [x] Doc states constraints: preserve schema validity, do not hide real findings, calibration must pass, thresholds justified and tested.
- **Status:** [x]

---

### Task 3: Implement emission gating and weak-signal handling

- **What:** In the orchestrator, add emission gating so that scans with extremely low confidence (below a justified minimum threshold) or with summary indicating "no real signals" (e.g. "No … signals detected") are suppressed from emission. Suppressed scans do not update StateDiffer and do not produce cleared events when they disappear. Document threshold and rationale.
- **Acceptance criteria:**
  - [x] Confidence gate: scans with confidence below documented threshold (e.g. 0.20) can be suppressed (no detection.observed / policy.evaluated emitted).
  - [x] Summary gate: scans whose action_summary indicates no real signals (e.g. matches "No … signals detected") can be suppressed when combined with low confidence or weak signals.
  - [x] Suppressed scans do not update state; no spurious cleared events for never-emitted tools.
  - [x] Threshold and rationale documented (e.g. in architecture doc or code comment).
- **Status:** [x]

---

### Task 4: Targeted wording and thresholds (scanners and scheduler)

- **What:** (Optional, minimal.) Improve action_summary wording for identity-only or artifact-only cases (e.g. "Environment or artifact hint only; no running X process or strong artifact" where scanners have that context). Optionally treat scheduler-only detections (file=0.5, all other signals 0) as suppressible via the same gating. No broad scanner redesign.
- **Acceptance criteria:**
  - [x] Where scanners set "No X signals detected" with only identity/env present, wording optionally clarified (e.g. hint vs detection) in 1–2 scanners or left to gating only.
  - [x] Scheduler-only scans either pass through gating (suppressed when confidence/summary qualify) or are explicitly documented. No unrelated scanner changes.
- **Status:** [x]

---

### Task 5: Add tests for weak-signal behavior and integration

- **What:** Add unit tests: emission gating suppresses detection/policy events for below-threshold or "no signals" scans; strong detections still emit. Run calibration tests; all must pass. Add integration test(s): one weak and one strong scan; assert strong present, weak absent (or downgraded).
- **Acceptance criteria:**
  - [x] Unit test(s): weak scan (low confidence or "No … signals detected") does not emit detection.observed / policy.evaluated when gating enabled.
  - [x] Unit test(s): strong scan still emits detection.observed and policy.evaluated.
  - [x] `pytest collector/tests/test_calibration.py -v` passes.
  - [x] Integration test: mix of weak and strong scans yields events only for strong (or as per gating design).
- **Status:** [x]

---

### Task 6: QA evidence and completion report

- **What:** Capture before/after terminal snippets (e.g. `detec-agent scan --verbose`), list of changed files, rationale for threshold/wording. Write completion report at `project-docs/detec-signal-credibility-completion-report.md` with status, what was changed, before/after summary, remaining limitations, validation summary.
- **Acceptance criteria:**
  - [x] QA evidence: before/after examples, changed files, rationale stored in project-docs or docs.
  - [x] `project-docs/detec-signal-credibility-completion-report.md` exists with: status (done/blocked), changed files, before/after summary, remaining limitations, validation summary.
- **Status:** [x]

---

## Completion

- Tasks 2–5 must pass QA before Task 6. Task 6 (completion report) is written after integration.
- Maximum 3 retries per task before marking blocked. EvidenceQA validates: weak cases improved, strong detections not regressed, schema-valid output, output more readable and credible.
