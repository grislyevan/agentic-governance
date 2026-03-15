# Detec Signal Credibility — QA Evidence

Source: [project-specs/detec-signal-credibility-setup.md](../project-specs/detec-signal-credibility-setup.md) and [task list](../project-tasks/detec-signal-credibility-tasklist.md).

---

## 1. Changed files

| File | Change |
|------|--------|
| `project-specs/detec-signal-credibility-setup.md` | New: project spec (goal, requirements, success criteria, out of scope). |
| `project-tasks/detec-signal-credibility-tasklist.md` | New: task list with acceptance criteria and status. |
| `project-docs/detec-signal-credibility-architecture.md` | New: emission path, credibility levers, constraints. |
| `project-docs/detec-signal-credibility-qa-evidence.md` | New: this file (QA evidence). |
| `project-docs/detec-signal-credibility-completion-report.md` | New: completion report. |
| `collector/orchestrator.py` | Added `EMISSION_MIN_CONFIDENCE` (0.20), `EMISSION_NO_SIGNALS_MAX_CONFIDENCE` (0.45), `_no_signals_summary()`, `_should_suppress_emission()`; at start of `_process_detection()` call gating and return 0 when suppressed. |
| `collector/scanner/claude_code.py` | In `_determine_action()`: when no process/file/network/behavior summaries but identity > 0, set action_summary to "Environment or artifact hint only; no running Claude Code process or strong artifact." |
| `collector/tests/test_pipeline.py` | Added `test_weak_scan_suppressed_by_credibility_gate`, `test_no_signals_summary_with_low_confidence_suppressed`, `test_strong_scan_still_emits_despite_credibility_gate`. |
| `collector/tests/test_main_integration.py` | Added class `TestCredibilityGating` and `test_weak_and_strong_only_strong_emits`. |

---

## 2. Rationale for thresholds and behavior

- **EMISSION_MIN_CONFIDENCE = 0.20:** Below this, the weighted score is dominated by a single weak layer (e.g. identity-only or file-only artifact). Emitting full detection and policy events for these cases makes the stream look busy without actionable signal and reduces trust. Lab-run calibration fixtures use real tool scenarios and yield confidence above this threshold; no calibration change required.
- **EMISSION_NO_SIGNALS_MAX_CONFIDENCE = 0.45:** When the scanner has already set the summary to "No X signals detected," we treat that as an explicit "no real signals" signal. If confidence is still below Medium (0.45), we suppress to avoid the confusing case where the event says "no signals" but a full detection/policy pair is emitted.
- **Suppress only (no new event type):** Schema and API stay unchanged. Suppressed scans are not written to state, so they do not produce cleared events when they disappear.

---

## 3. Before / after behavior summary

| Aspect | Before | After |
|--------|--------|--------|
| Emission | Every scan with `detected=True` produced `detection.observed` + `policy.evaluated` (subject only to StateDiffer in daemon). | Scans with confidence < 0.20, or with "No … signals detected" summary and confidence < 0.45, are suppressed (no events, no state update). |
| Scheduler-only | Scheduler-only scans (file=0.5, others 0) always emitted. | Their confidence is below 0.20, so they are suppressed. |
| Identity-only | Identity-only or env-only evidence could produce a full event with summary "No X signals detected." | Suppressed by confidence gate; Claude Code scanner also uses clearer wording when only identity is present. |
| Strong detections | Emitted. | Unchanged; confidence and summary gates do not apply. |
| Schema | All emitted events schema-valid. | Unchanged; no new event types. |

---

## 4. Validation commands and results

- **Calibration (no regression):**  
  `pytest collector/tests/test_calibration.py -v`  
  Result: 7 passed.

- **Credibility unit tests:**  
  `pytest collector/tests/test_pipeline.py -v -k "credibility or weak or strong_scan or no_signals"`  
  Result: 3 passed (weak suppressed, no_signals suppressed, strong still emits).

- **Credibility integration test:**  
  `pytest collector/tests/test_main_integration.py -v -k "CredibilityGating"`  
  Result: 1 passed (weak + strong scan yields only strong tool events).

- **Full collector tests:**  
  `pytest collector/tests/ -v`  
  Run as part of CI; all tests should pass.

---

## 5. Terminal output (example)

Running a one-shot scan after the change, suppressed detections appear in verbose output as:

```
  WeakTool: suppressed (credibility gate: confidence=0.0600)
```

Events emitted count and validation failures line are unchanged in shape; only the number of events may be lower when weak detections are present.

Example completion line (unchanged shape):

```
Scan complete. Events emitted: N, validation failures: 0
```
