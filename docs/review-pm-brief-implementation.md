# Dev-Eng Review: PM Brief Implementation (2026-03-12)

**Scope:** Implementation of the Detec PM Brief plan (behavioral/ESF, Claude Code confidence, uncalibrated scanners, ISO-001, cron/LaunchAgent, LAB-RUN-015, Cowork in main, API/messaging, PROGRESS tracking).

**Reviewers:** Multi-disciplinary engineering lens (security, performance, reliability, operability, testability).

---

## Summary

The implementation matches the plan and is suitable to ship. One bug was fixed (enforcer `dry_run` not guaranteeing `simulated=True`), and one test-hardening change was made (isolated state dir for enforcement e2e tests). A few minor follow-ups are recommended.

---

## What Was Reviewed

| Area | Files | Verdict |
|------|--------|--------|
| Scheduler artifact scanning | `collector/scanner/scheduler_artifacts.py`, `collector/main.py` (Stage 1e) | OK; see notes below |
| Claude Code weights + Cowork in main | `collector/engine/confidence.py`, `collector/main.py` | OK |
| ISO-001 wording | `api/core/baseline_policies.py`, `docs/enforcement-roadmap.md` | OK |
| ESF/behavioral docs | `docs/esf-entitlement.md`, playbook Section 3 | OK |
| Cowork schedule-skill | `collector/scanner/claude_cowork.py` | OK |
| Enforcement e2e | `collector/enforcement/enforcer.py`, `collector/tests/test_enforcement_e2e.py` | Bug fix + test isolation applied |

---

## Security

- **Scheduler artifact module:** Reads only user crontab (`crontab -l`), `/etc/cron.d/`, and LaunchAgent plists. No arbitrary command execution; subprocess is fixed (`crontab -l`) with timeout. Plist parsing uses `plistlib.loads(bytes)`; no `eval` or unsafe deserialization. Acceptable.
- **System paths:** Reading `/etc/cron.d/` and `/Library/LaunchAgents/` may require root on locked-down systems; the code handles `PermissionError` and logs at debug. Document in deploy docs that scheduler evidence for system cron/LaunchAgents is best-effort unless the agent runs with sufficient privileges.
- **No new secrets:** No credentials or tokens in new code.

---

## Performance

- **Scheduler scan:** Runs once per scan cycle. `get_scheduler_entries()` does a few file reads and one subprocess call; cost is small. No caching; acceptable for typical scan intervals (e.g. 300s).
- **Merge loop in main:** O(detected_scans × scheduler_entries); both are small. No concern.
- **Plist size:** `_read_launch_agent_plist` reads full file into memory. LaunchAgent plists are typically small (&lt; 10 KB). Optional follow-up: cap read size (e.g. 1 MB) to avoid a hostile plist.

---

## Reliability

- **Enforcer dry_run:** Previously, with `dry_run=True` and posture from PostureManager (e.g. "active"), the enforcer could hit the allow-list or other branches and return a result without `simulated=True`. **Fix applied:** When `dry_run` is True, the enforcer now short-circuits immediately after the detect/warn branch and always returns `_simulate(...)`, so `simulated=True` is guaranteed. This matches the documented intent of dry-run.
- **Scheduler exception handling:** Stage 1e is wrapped in try/except; a scheduler failure logs and skips without failing the scan. Good.
- **Test isolation:** `test_step4_5_enforcement_simulated` and `test_step6_enforcement_active_kill` previously used `PostureManager(..., state_dir=None)`, so they loaded state from `~/.agentic-gov`. That could make step 6 flaky (e.g. allow-list matching "Unknown Agent"). **Fix applied:** Both tests now use `tempfile.TemporaryDirectory()` and pass `state_dir=Path(state_dir)` so posture state is empty and isolated.

---

## Operability

- **Logging:** Scheduler and main use `logger.warning` / `logger.debug` appropriately. No new log noise at INFO.
- **Verbose output:** When `args.verbose` is True, Stage 1e prints scheduler artifact and scheduler-only detection messages. Consistent with the rest of the pipeline.

---

## Testability

- **Scheduler:** `test_scheduler_artifacts.py` covers `_match_binary`, `get_scheduler_evidence_by_tool`, and integration with mocked crontab/cron_dir/LaunchAgent. Good coverage for the new module.
- **Main pipeline:** All `run_scan` tests in `test_main_integration.py` mock `get_scheduler_evidence_by_tool` and `ClaudeCoworkScanner`; clean and single-detection scenarios are stable.
- **Calibration:** `test_calibration.py` passes with the new `CLAUDE_CODE_WEIGHTS` and existing LAB-RUN-001 fixture range.
- **Enforcement e2e:** All 8 tests in `test_enforcement_e2e.py` pass after the enforcer fix and state-dir isolation.

---

## Cross-Cutting Checklist

| Concern | Status |
|--------|--------|
| Security (input validation, auth, secrets) | OK; no new attack surface; plist/cron input is bounded. |
| Performance (N+1, caching, async) | OK; scheduler cost is small and linear. |
| Reliability (error handling, retries) | OK; scheduler failures are caught; dry_run behavior fixed. |
| Operability (logging, health, config) | OK; existing patterns followed. |
| Testability (coverage, injectability) | OK; new code tested; tests isolated. |

---

## Recommended Follow-Ups (Non-Blocking)

1. **Scheduler:** Document in DEPLOY.md or SERVER.md that reading `/etc/cron.d/` and `/Library/LaunchAgents/` may require elevated privileges on some systems; scheduler evidence for those paths is best-effort.
2. **Plist read cap:** Consider limiting plist read size in `_read_launch_agent_plist` (e.g. 1 MB) to avoid unbounded memory use on malformed or hostile plists.
3. **Calibrated vs synthetic:** The lab index now states which tools are calibrated vs synthetic; keep that table updated as LAB-RUN-008 (Aider) and LAB-RUN-015 are completed.

---

## Changes Made During Review

1. **Enforcer dry_run guarantee** ([collector/enforcement/enforcer.py](collector/enforcement/enforcer.py))  
   When `self._dry_run` is True, the enforcer now returns `_simulate(...)` immediately after the detect/warn branch, so every result in dry-run mode has `simulated=True`. This fixes the failing `test_step4_5_enforcement_simulated` and matches documented behavior.

2. **Enforcement e2e test isolation** ([collector/tests/test_enforcement_e2e.py](collector/tests/test_enforcement_e2e.py))  
   - `test_step4_5_enforcement_simulated` and `test_step6_enforcement_active_kill` now create a `tempfile.TemporaryDirectory()` and pass it as `state_dir` to `PostureManager`, so tests do not depend on `~/.agentic-gov` and are repeatable.

---

**Sign-off:** Implementation is in good shape for production use. The fixes applied improve correctness (dry_run) and test reliability (state isolation). Recommended follow-ups are documentation and a small hardening (plist size cap) and can be done in a later change.
