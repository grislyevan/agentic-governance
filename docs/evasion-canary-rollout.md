# Canary Rollout for Evasion Policy Updates (INIT-31 E4)

When changing evasion-related policy (tamper floor, new rules, or enforcement defaults), use a staged rollout to limit blast radius.

## Controls

1. **Tenant or profile scoping**
   - Prefer server-pushed policy (posture, auto_enforce_threshold, allow list) per endpoint or tenant. Roll out new evasion rules or floor behavior to a canary tenant or canary profile first.
   - Use the API to assign a subset of endpoints to a "canary" policy or posture (e.g. a policy set that includes the new tamper floor or stricter defaults).

2. **Collector config**
   - Use config file or env (e.g. `AGENTIC_GOV_ENFORCEMENT_POSTURE=audit`) on canary endpoints so actions are simulated. After validating events and logs, switch to `active` for that group.
   - High-collateral options (e.g. `allow_linux_uid_block_fallback`) should be enabled only on explicitly designated endpoints; do not enable globally by default.

3. **Validation**
   - Run evasion regression before and after: `pytest collector/tests/test_evasion_suite.py collector/tests/test_evasion_suite_runtime.py -q`.
   - Monitor canary endpoints for false positives (unexpected blocks or approval_required) and for missed detections. Use session reports and `evasion_vectors` to verify.

4. **Rollback**
   - If canary shows issues, revert policy or posture for that group via server push or config. See [evasion-controls-rollback.md](evasion-controls-rollback.md).

## Implementation note

Canary behavior is achieved through existing mechanisms: server-pushed posture/threshold, per-endpoint config, and policy API. No new "canary flag" is required; use tenant/profile assignment and config to define the canary set.
