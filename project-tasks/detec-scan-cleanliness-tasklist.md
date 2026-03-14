# Detec Scan Cleanliness: Task List

**Spec:** Scan cleanliness and schema validation correctness only. No collector redesign.

## Tasks

- [x] 1. **Reproduce and isolate** – Run `detec scan --verbose` and `detec-agent scan --verbose`; capture exact validation error messages and counts; optionally add a small test that reproduces the three failure shapes (action.type, outcome.enforcement_result, correlation_context) against EventValidator. Document the baseline.
- [x] 2. **Fix schema/payload mismatch** – (a) Normalize `action.type` in `build_event` to a schema-allowed value when scanner sends approval_required/warn/none. (b) Add `"simulated"` to `outcome.enforcement_result` enum in canonical schema. (c) Add optional `correlation_context` to canonical schema root and to API `_ALLOWED_TOP_LEVEL_KEYS`. Run collector and API tests; fix any breakages.
- [x] 3. **Improve scan output clarity (if needed)** – Only if completion line or surrounding output is confusing after fixes; keep messaging truthful and operationally useful.
- [x] 4. **Update minimal docs/demo evidence** – Update README or demo snippet only if expected output or recommended command changes; ensure task list and completion report reference corrected behavior.
- [x] 5. **Final QA / integration** – Re-run recommended demo scan path; confirm zero schema validation failures in successful case; capture terminal output and changed files; write short completion report with status and remaining limitations.

## Baseline (Task 1)

- Scan: `detec-agent scan --verbose` with `AGENTIC_GOV_TELEMETRY_PROVIDER=polling`: **Events emitted: 16, validation failures: 9** (exit code 1).
- Three failure shapes reproduced in `collector/tests/test_validator.py`: `test_scan_cleanliness_baseline_action_type_fails`, `test_scan_cleanliness_baseline_enforcement_result_simulated_fails`, `test_scan_cleanliness_baseline_correlation_context_fails`.

## Task 4 note

README one-minute demo already shows "validation failures: 0" as the expected output; no README change was required. Task list and this completion status document the corrected behavior.

## Success criteria

- Recommended demo scan completes with validation failures: 0.
- Event payloads conform to expected schema.
- CLI output suitable for README/live demo.
- Existing scan functionality preserved.
- Changes minimal and scoped to scan correctness and polish.
