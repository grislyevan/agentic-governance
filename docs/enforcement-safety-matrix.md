# Enforcement Safety Matrix (INIT-31 E4)

This matrix documents which enforcement actions are allowed per OS and profile when policy (including evasion/tamper floor) triggers block or approval_required. High-collateral tactics require explicit opt-in.

## Scope

- **Evasion-triggered:** When `agent_status.tamper_vectors` or evasion findings elevate the policy decision (tamper floor), the same enforcement ladder applies. This matrix bounds **all** block/approval_required actions, including those driven by evasion.
- **Profile:** Collector enforcement posture (passive / audit / active) and optional per-deployment config (e.g. `allow_linux_uid_block_fallback`).

## Tactics by OS

| OS | Tactic | Collateral risk | Default allowed | Opt-in / notes |
|----|--------|-----------------|-----------------|----------------|
| **macOS** | Process kill (SIGTERM then SIGKILL) | Target process tree only | Yes (when posture is active) | None |
| **macOS** | Network block (pfctl by user) | All outbound from that user | Yes (when posture is active) | Blocks by user; same UID as target PID |
| **Linux** | Process kill | Target process tree only | Yes (when posture is active) | None |
| **Linux** | Network block (cgroup v2 + iptables) | Target PID only | Yes (when posture is active) | Preferred when cgroup v2 and net_cls available |
| **Linux** | Network block (iptables --uid-owner fallback) | **All processes owned by that UID** | **No** | Set `allow_linux_uid_block_fallback=true` in config or `AGENTIC_GOV_ALLOW_LINUX_UID_BLOCK_FALLBACK=1` to allow. High collateral: browser, IDE, shells under same user lose outbound. |
| **Windows** | Process kill | Target process tree only | Yes (when posture is active) | None |
| **Windows** | Network block (netsh by executable path) | Same executable path only | Yes (when posture is active) | Scoped by program path |

## Posture behavior

| Posture | Block / approval_required behavior |
|---------|------------------------------------|
| **passive** | Log and emit events only; no OS-level enforcement |
| **audit** | Compute tactic and emit event with `simulated=True`; no OS-level enforcement |
| **active** | Execute tactic when confidence >= threshold; network block subject to matrix above |

## Evasion and tamper

When the tamper floor (INIT-31 E3) elevates a decision to `warn` or `approval_required`, enforcement still follows the same tactics and matrix. No separate "evasion-only" actions; the safety conditions above apply uniformly.

### Tamper floor mapping (E3-03)

When `agent_status.tamper_vectors` is non-empty, the policy engine applies a minimum response floor (see `collector/engine/policy.py`):

| Vectors | Minimum response |
|---------|------------------|
| E6-agent-kill-loop, E7-config-tamper, E8-telemetry-shaping, capability_drift | approval_required |
| E1-global-hook, E1-repo-hook, E2-template-hook, E3-force-push, E4-renamed-binary, E5-cursor-git-disabled, E5-cursor-telemetry-off | warn |

The floor is the maximum of the base policy decision and the minimum for any vector present. Unknown vector IDs default to detect.

## Rollback

See [docs/evasion-controls-rollback.md](evasion-controls-rollback.md) for post-deploy verification and rollback steps specific to evasion and enforcement controls.
