# Evasion Controls: Post-Deploy Verification and Rollback (INIT-31 E4)

## Post-deploy verification

After deploying evasion-related changes (tamper floor, policy defaults, enforcement safety gating, or CI evasion suite):

1. **API / collector compatibility**
   - Confirm API accepts events with `agent_status.tamper_vectors` and stores them (session aggregation uses them for reports).
   - Run a one-shot collector with a policy that would trigger tamper floor: `detec-agent --dry-run --verbose` and confirm no crashes; check logs for "tamper_vectors" or "tamper floor" if applicable.

2. **Enforcement safety**
   - On Linux, with default config, confirm network block does **not** use UID fallback when cgroup v2 is unavailable (log should show "Skipping UID fallback").
   - With `allow_linux_uid_block_fallback=true` (or env), confirm UID fallback is used only when explicitly enabled.

3. **Evasion regression**
   - Run: `pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -q`
   - In CI, confirm the "Evasion Regression (INIT-31)" job passes and artifact `evasion-metrics-initial-31` is produced.

4. **Policy and reporting**
   - `pytest collector/tests/test_policy.py api/tests/test_session_reports.py -q` (or the subset that covers tamper floor and evasion_vectors).

## Rollback procedure

If evasion controls cause regressions (e.g. over-blocking, collector crashes, or API validation failures):

1. **Immediate**
   - Revert the deploying commit(s) and redeploy. Prefer a single logical revert (e.g. "Revert INIT-31 E3: tamper floor and reporting") so rollback is traceable.

2. **Collector-only**
   - If the issue is collector-side (e.g. tamper floor too aggressive): disable or relax policy on the server (policy API), or set collector to `dry_run=true` / `enforcement_posture=passive` so no OS-level enforcement runs while you fix.

3. **API / session reports**
   - If session aggregation or report schema breaks: revert API/schema changes first; collectors can continue sending events (older API may ignore `agent_status`). Re-enable after fixing.

4. **CI**
   - If the evasion regression job blocks releases: temporarily skip or remove the job in `.github/workflows/ci.yml` and open an issue to fix the suite; do not leave skipped indefinitely.

## Dry-run validation

Before rolling out enforcement or policy changes:

- Run collector with `--dry-run` and `enforcement_posture=active` (or audit) to see simulated actions without executing them.
- Run the full test set: `pytest collector/tests/test_enforcement_hardening.py collector/tests/test_cgroup_network_block.py collector/tests/test_policy.py api/tests/test_enforcement_router.py -q`.
