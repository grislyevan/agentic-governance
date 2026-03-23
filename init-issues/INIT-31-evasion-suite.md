# INIT-31 — Evasion Suite (Full Deep Revision)

## Scope
Issue: **INIT-31**
Objective: define a rigorous evasion testing suite that measures how detection and governance controls behave under deliberate bypass conditions, not just happy-path usage.

The evasion suite is intended to:
- quantify resilience,
- expose blind spots early,
- prevent overconfident claims,
- and guide mitigation prioritization.

---

## 1) Why an Evasion Suite Is Mandatory
AI tool detection systems fail in production when they are tuned only for expected behavior.

Attackers, power users, and even normal developers can unintentionally create evasive conditions through:
- wrappers/aliases,
- containerized workflows,
- custom backends,
- partial telemetry environments.

A formal evasion suite transforms these from unknown unknowns into measurable, trackable risk dimensions.

---

## 2) Evasion Suite Design Principles
1. **Adversarial realism**
   - tests should mimic practical bypass methods, not toy cases.
2. **Class coverage**
   - include SaaS copilots, local runtimes, and autonomous executors.
3. **Deterministic replayability**
   - evasion scenarios must be rerunnable with stable IDs.
4. **Outcome granularity**
   - capture degrade modes (confidence drop, wrong decision, missing evidence), not just pass/fail.
5. **Mitigation linkage**
   - every evasion failure maps to a mitigation owner and timeline.

---

## 3) Evasion Category Taxonomy

### Category E1 — Binary/Entry-Point Obfuscation
Examples:
- renamed binaries,
- wrapper scripts,
- alias/function indirection,
- alternate launchers.

Expected pressure point:
- process attribution reliability.

---

### Category E2 — Environment Isolation
Examples:
- container/devcontainer execution,
- ephemeral virtualenvs,
- remote workspace/SSH-based execution.

Expected pressure point:
- host telemetry completeness and lineage continuity.

---

### Category E3 — Network Attribution Ambiguity
Examples:
- shared model gateways,
- corporate proxy routing,
- custom API relay endpoints,
- mixed backend paths.

Expected pressure point:
- tool/backend attribution confidence.

---

### Category E4 — Artifact Evasion
Examples:
- non-default config/model paths,
- artifact cleanup post-run,
- transient state storage.

Expected pressure point:
- forensic traceability and post-event reconstruction.

---

### Category E5 — Policy Boundary Probing
Examples:
- repeated near-threshold risky actions,
- scope-boundary edge cases,
- exception misuse attempts.

Expected pressure point:
- enforcement ladder consistency and anti-abuse controls.

---

## 4) Scenario Definition Schema
Each evasion scenario must include:
- `evasion_scenario_id`
- `matrix_cell_id` (link to INIT-28)
- `tool_id` + `tool_class`
- `evasion_category` (E1..E5)
- `attack_technique_description`
- `preconditions`
- `action_sequence`
- `expected_degradation_profile`
- `expected_policy_behavior`
- `required_evidence_outputs`
- `pass_fail_criteria`

Optional:
- mapped ATT&CK-style technique reference,
- historical incident linkage.

---

## 5) Degradation Outcome Model
Evasion runs should classify outcomes as:

### R0 — Resilient
- detection/decision behavior remains within expected tolerance.

### R1 — Partial Degradation (acceptable)
- confidence drops but policy behavior remains safe.

### R2 — Material Degradation
- confidence or explainability meaningfully impaired; policy decision still defensible but risky.

### R3 — Control Failure
- incorrect decision, missed detection, or unsafe allow action.

This scale enables prioritized remediation over binary pass/fail simplification.

---

## 6) Core Metrics for Evasion Resilience
- **Evasion Success Rate** (how often bypass materially degrades controls)
- **Decision Drift Rate under Evasion**
- **Confidence Penalty Quality** (did score degrade appropriately?)
- **Safe-Fallback Rate** (did system move to warn/approval/block conservatively?)
- **Evidence Survivability Rate** (was enough evidence retained for audit?)

Metrics must be segmented by:
- tool class,
- sensitivity tier,
- action risk class,
- deployment context.

---

## 7) Required Assertions per Evasion Run
1. **Detection assertion**
   - system must still detect or explicitly classify uncertainty.
2. **Confidence assertion**
   - score must reflect degraded certainty, not remain falsely high.
3. **Decision assertion**
   - enforcement must remain safe for risk context.
4. **Explainability assertion**
   - reason codes and uncertainty notes present.
5. **Evidence assertion**
   - minimum evidence set preserved even under evasion.

---

## 8) Mitigation Mapping Workflow
For every R2/R3 outcome, record:
- root-cause category,
- impacted controls,
- proposed mitigation,
- mitigation owner,
- target release,
- residual risk after fix.

No unresolved high-risk evasion should be hidden behind aggregate pass rates.

---

## 9) Release Gating with Evasion Results
Suggested gates:
- no unresolved R3 failures in Tier2/3 high-risk scenarios,
- bounded R2 rate with explicit approved exceptions,
- required confidence penalty behavior present for known evasions,
- evidence survivability above minimum threshold.

If gates fail, release should block or require explicit risk acceptance.

---

## 10) Failure Modes and Safeguards

### Failure Mode: Evasion tests become stale
Safeguard:
- periodic refresh from real-world telemetry and incident learnings.

### Failure Mode: Only low-difficulty evasions tested
Safeguard:
- include mandatory high-impact adversarial scenarios per class.

### Failure Mode: Hidden unsafe fallback behavior
Safeguard:
- explicit decision assertions in every evasion scenario.

### Failure Mode: Teams ignore evasion findings
Safeguard:
- mitigation tracking tied to release criteria and ownership accountability.

---

## 11) Reporting Requirements
Evasion suite reports should include:
- category-wise resilience scores,
- top failing scenarios by business impact,
- trend of R2/R3 over releases,
- unresolved mitigation backlog,
- confidence calibration under evasion stress.

Buyer-safe version should include:
- known evasion classes tested,
- current resilience posture,
- transparent limitations and roadmap.

---

## 12) Validation Plan
1. implement baseline E1-E5 scenarios for at least one Class A/B/C tool each.
2. verify degradation outcome model classification consistency.
3. validate mitigation linkage workflow end-to-end.
4. generate first evasion resilience report.

Required artifacts:
- evasion scenario catalog,
- resilience metrics dashboard snapshot,
- remediation backlog export.

---

## 13) Buyer-Credibility Statement
"We test not just whether detection works, but how it fails under adversarial conditions. Our evasion suite measures resilience, documents limitations, and ties every meaningful weakness to an accountable mitigation path."

---

## 14) Acceptance Checklist
- [x] Evasion taxonomy and scenario schema defined.
- [x] Degradation outcome model and resilience metrics documented.
- [x] Assertion requirements and mitigation workflow specified.
- [x] Release-gating logic and reporting requirements defined.
- [x] Failure modes and safeguards captured.
- [ ] Empirical evasion run evidence attached.
