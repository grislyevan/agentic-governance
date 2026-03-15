# Detec Signal Credibility — Architecture and Credibility Levers

For implementers and QA. Source: [project-specs/detec-signal-credibility-setup.md](../project-specs/detec-signal-credibility-setup.md) and [task list](../project-tasks/detec-signal-credibility-tasklist.md).

---

## 1. Purpose and scope

- **Goal:** Improve scan result credibility by reducing noisy, weak, or confusing detections so output feels intentional and trustworthy. Detections should feel grounded; weak evidence should be handled intentionally; low-confidence cases should not be overstated.
- **In scope:** Emission gating, targeted wording, optional attribution thresholds, tests, and documentation. No scoring-model redesign, no policy-engine rebuild, no new detection taxonomy, no dashboard or packaging work.

---

## 2. Current emission path

Events are produced in a single pipeline per scan cycle:

1. **Collection:** `run_scan()` in `collector/orchestrator.py` runs all scanners (and behavioral, evasion, MCP, scheduler artifacts). Each scanner returns a `ScanResult` with `detected=True` when any layer has signal &gt; 0.
2. **Aggregation:** All scans with `detected=True` are gathered into `detected_scans`. Scheduler-only scans (file=0.5, other signals 0) are appended as additional `ScanResult` entries.
3. **Per-scan processing:** For each scan in `detected_scans`, `_process_detection()` is called. It:
   - Computes confidence via `compute_confidence(scan)` and classifies it (Low/Medium/High).
   - Evaluates policy via `evaluate_policy(...)`.
   - Optionally checks `StateDiffer.is_changed()` (daemon mode); if unchanged, returns 0 and does not emit.
   - Builds `detection.observed` and `policy.evaluated` events via `build_event()` and emits them via `emitter.emit()`. Optionally builds and emits enforcement events.
   - If state_differ is used and events were emitted, updates state via `state_differ.update()`.
4. **Cleared events:** After processing all detections, `_emit_cleared_events()` emits `detection.cleared` for tools that were previously emitted as detected but are no longer in `detected_tools`.

**Gap:** There is no step that filters or downgrades scans by confidence or by summary quality before emission. Every `detected=True` scan currently produces a full detection + policy event chain (subject only to StateDiffer in daemon mode).

---

## 3. Where credibility interventions fit

Credibility changes belong in one or both of:

- **Before the emission loop:** After `detected_scans` is built, filter or tag scans that should not be emitted (e.g. "suppress" list). The loop then calls `_process_detection()` only for scans that pass the credibility gate. Suppressed scans are not added to the set that StateDiffer considers "currently detected," so they do not drive cleared events when they disappear.
- **Inside `_process_detection()`:** Before building events, compute confidence and apply a gate (e.g. if confidence below threshold or summary indicates no real signals, return 0 without emitting and without updating state). This keeps all logic in one place and avoids mutating `detected_scans` or the "detected_tools" set used for cleared events; the caller must treat "suppressed" scans as not emitted for state purposes (e.g. do not add their tool name to the set used by `cleared_tools()`).

Either way, suppressed scans must:
- Not result in `detection.observed` or `policy.evaluated` (or enforcement) events.
- Not update StateDiffer (so they are not "last emitted as detected").
- Not cause `detection.cleared` when they disappear (because they were never emitted as detected).

---

## 4. Credibility levers

### 4.1 Emission gating (primary)

- **Confidence gate:** Do not emit detection/policy events for scans whose final confidence is below a **justified minimum threshold** (e.g. 0.15 or 0.20). Rationale: extremely low confidence indicates identity-only or artifact-only evidence that is not actionable; emitting full events for these reduces trust. Threshold must be documented and tested; calibration fixtures (which use real lab-run signals) should remain above the gate.
- **Summary gate:** Do not emit (or treat as suppressible) when `action_summary` indicates no real signals, e.g. matches a pattern like "No … signals detected." Many scanners set this fallback when only identity/env evidence exists. Combined with low confidence, such scans are good candidates for suppression.
- **Implementation:** A single helper (e.g. `_should_suppress_emission(scan, confidence)`) can encapsulate: confidence &lt; threshold, or (confidence below threshold and summary matches "no signals" pattern). Suppression is "do not emit"; no new event type (e.g. "hint") unless the schema is extended later.

### 4.2 Attribution thresholds (optional, per spec)

- Per-scanner or global rules such as "require at least one of process, file, or behavior above a small floor before treating as detected for emission" are **optional** and should be applied only where clearly justified (e.g. 1–2 noisiest tools). Prefer emission gating in the orchestrator over broad scanner changes to avoid redesign.
- **Scheduler-only:** Scans created from scheduler artifacts only (file=0.5, process/network/identity/behavior 0) are passed through the same emission gate. Their computed confidence (file layer only) is typically below `EMISSION_MIN_CONFIDENCE`, so they are suppressed and do not emit. No separate exclusion or tagging is required.

### 4.3 Wording (targeted)

- Where scanners set `action_summary` to "No X signals detected" when only identity or environment evidence is present, consider clarifying to something like "Environment or artifact hint only; no running X process or strong artifact" in 1–2 scanners where the context is already available. This is optional; emission gating alone already prevents these from being emitted if confidence is below threshold. Do not add new detectors or change scanner contracts broadly.

### 4.4 Extension-host and ambiguous attribution

- Rely on **existing penalties** (e.g. `extension_host_shared_by_all_extensions`, `extension_host_ambiguity`) plus **emission gating**. If extension-host-only cases already score low confidence, the confidence gate will suppress them. If a specific rule is needed later (e.g. suppress when extension_host_ambiguity penalty present and no process evidence), add it as a single documented branch in the gating logic.

---

## 5. Constraints

- **Schema-valid output:** All emitted events must continue to conform to the canonical JSON Schema. No new event types unless the schema is updated and justified.
- **Do not hide real findings:** Suppression applies only to extremely weak, non-actionable cases (very low confidence and/or summary indicating no real signals). Strong detections and medium-confidence detections must still be emitted.
- **Calibration tests must pass:** `pytest collector/tests/test_calibration.py -v` must pass. The confidence formula and band boundaries are unchanged; gating is applied after confidence is computed. Lab-run fixtures represent real tool scenarios and should remain above the emission threshold.
- **Thresholds justified and tested:** Any minimum confidence threshold (e.g. 0.20) must be documented with rationale and have unit and integration tests that verify weak scans are suppressed and strong scans are not.

---

## 6. Validation (for EvidenceQA and integration)

- **Per task:** Gating logic is in place; threshold and rationale documented; unit tests show weak suppressed and strong emitted; calibration tests pass; integration test covers mix of weak and strong scans.
- **Final:** Before/after terminal snippets, list of changed files, and completion report with status, before/after summary, remaining limitations, and validation summary.
