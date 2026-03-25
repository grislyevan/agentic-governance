# Policy Simulation Packs

These profiles are starting points for pilot policy tuning. They define posture and rule overrides for three common operating modes. Each pack is a reference configuration for operators — the JSON files are not direct API request payloads. Apply them by reviewing the profile, configuring posture via Enforcement settings in the dashboard, and adjusting individual policy rules to match.

---

## Profile Summary

| Profile | Posture | Low confidence | Medium confidence | High confidence | Class D | Recommended phase |
|---|---|---|---|---|---|---|
| `visibility-only` | passive | detect | detect | detect | detect | Days 1–14: initial baseline capture |
| `warn-heavy` | audit | detect | warn | warn | approval_required | Days 14–30: post-baseline tuning |
| `approval-required-high-risk` | audit (active for Class D if enabled) | detect | warn | approval_required | block | Post-pilot: sustained production use |

---

## How to Apply

1. Review the profile JSON to understand which rules are overridden and why.
2. Configure posture via **Enforcement** settings in the dashboard (passive / audit / active).
3. Adjust individual policy rules to match the `override_decision` values in the profile.
4. For overlay rules in `approval-required-high-risk`, add or activate them in the Policy Studio.

**Do not apply `warn-heavy` or `approval-required-high-risk` without first running `visibility-only` for at least one week and reviewing your false-positive rate.** Skipping the baseline phase means you do not know whether your environment's FP rate is acceptable before enforcement decisions begin generating analyst workload or holding tool activity.

---

## Tradeoffs

**visibility-only**
No enforcement actions fire. False positives have zero operational impact. All detections are logged for review. Use this phase to establish baseline event volume, identify FP-prone processes, and populate the allow-list before escalating posture. The cost is zero protection during this window.

**warn-heavy**
Analyst notifications fire on Medium and High confidence detections. Under `audit` posture, enforcement decisions are logged but not applied, so tool activity is not interrupted. The FP cost is alert noise — analysts will triage warn decisions that turn out to be benign. Calibrate allow-list entries before escalating further.

**approval-required-high-risk**
High-confidence detections hold tool activity pending analyst review. A false positive at High confidence interrupts legitimate tool use until resolved. Class D block rules only take effect if posture is switched to `active`. This profile has the highest analyst workload and the strongest protection. It is appropriate after the FP rate is confirmed low enough that holds will not create operational friction.

---

Related: [docs/pilot-runbook.md](../../docs/pilot-runbook.md) | [docs/soc-analyst-workflow.md](../../docs/soc-analyst-workflow.md) | [docs/known-limitations.md](../../docs/known-limitations.md)
