# Detec Signal Credibility — Completion Report

Source: [project-specs/detec-signal-credibility-setup.md](../project-specs/detec-signal-credibility-setup.md) and [task list](../project-tasks/detec-signal-credibility-tasklist.md).

---

## Status

**Done.** All six tasks are complete. No tasks blocked.

---

## What was changed

1. **Spec and task list**  
   Added `project-specs/detec-signal-credibility-setup.md` and `project-tasks/detec-signal-credibility-tasklist.md` with goal, requirements, success criteria, deliverables, and out-of-scope.

2. **Foundation/architecture**  
   Added `project-docs/detec-signal-credibility-architecture.md` describing the emission path, credibility levers (emission gating, optional attribution thresholds, wording), and constraints (schema validity, no hiding real findings, calibration must pass).

3. **Emission gating**  
   In `collector/orchestrator.py`:
   - `EMISSION_MIN_CONFIDENCE = 0.20`: below this, no detection/policy events are emitted.
   - `EMISSION_NO_SIGNALS_MAX_CONFIDENCE = 0.45`: when `action_summary` indicates "No … signals detected" and confidence is below this, emission is suppressed.
   - `_no_signals_summary(scan)` and `_should_suppress_emission(scan, confidence)` implement the gate.
   - At the start of `_process_detection()`, if the gate applies, the function returns 0 without emitting or updating state.

4. **Targeted wording**  
   In `collector/scanner/claude_code.py`, when there are no process/file/network/behavior summaries but identity > 0, `action_summary` is set to "Environment or artifact hint only; no running Claude Code process or strong artifact." Scheduler-only behavior is documented in the architecture doc (they pass through the gate and are typically suppressed).

5. **Tests**  
   - **Unit (test_pipeline.py):** `test_weak_scan_suppressed_by_credibility_gate`, `test_no_signals_summary_with_low_confidence_suppressed`, `test_strong_scan_still_emits_despite_credibility_gate`.
   - **Integration (test_main_integration.py):** `TestCredibilityGating::test_weak_and_strong_only_strong_emits`.
   - **Calibration:** `pytest collector/tests/test_calibration.py -v` passes (7 tests).

6. **QA evidence and completion report**  
   Added `project-docs/detec-signal-credibility-qa-evidence.md` (changed files, rationale, before/after summary, validation commands) and this completion report.

---

## Before / after summary

- **Before:** Every scan with `detected=True` produced a full detection and policy event (except when StateDiffer skipped unchanged state in daemon mode). Identity-only or "No X signals detected" cases could still emit.
- **After:** Scans with confidence &lt; 0.20, or with "No … signals detected" and confidence &lt; 0.45, are suppressed. Strong detections are unchanged. Schema-valid output is preserved; no new event types.

---

## Remaining limitations

- Gating is based on a fixed threshold (0.20) and a summary pattern. Future tools or wording changes may require revisiting the pattern or adding tool-specific rules.
- Extension-host and shared-process cases rely on existing penalties plus the confidence gate; no separate "extension_host_ambiguity" branch was added. If real runs show medium-confidence extension-host-only noise, a small additional rule could be added.
- Only Claude Code received the identity-only wording change; other scanners still use "No X signals detected" when summaries are empty. Gating already suppresses those when confidence is low; wording can be extended to other scanners later if needed.

---

## Validation summary

- Calibration: 7/7 passed.  
- Credibility unit tests: 3/3 passed.  
- Credibility integration test: 1/1 passed.  
- Existing `_process_detection` and run_scan tests: pass.  
- Schema: no new event types; emitted events remain schema-valid.

Evidence and rationale are recorded in [detec-signal-credibility-qa-evidence.md](detec-signal-credibility-qa-evidence.md).
