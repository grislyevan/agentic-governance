# INIT-38 — Severity Taxonomy (Full Deep Revision)

## Scope
Issue: **INIT-38**
Objective: define a severity taxonomy that consistently maps AI-agentic events to operational urgency, enforcement posture, and response expectations.

This taxonomy must support:
- policy decisions,
- SOC triage,
- incident escalation,
- customer-facing risk communication.

---

## 1) Why Severity Taxonomy Is Foundational
Without a strict severity model, organizations get:
- inconsistent analyst responses,
- noisy escalations,
- weak SLA alignment,
- poor cross-team communication.

For agentic AI events, severity needs to reflect not only event type, but confidence, action impact, sensitivity context, and repeat behavior.

---

## 2) Severity Levels (Canonical)

### S0 — Informational
Definition:
- benign or low-confidence observations with no immediate risk indicator.

Examples:
- first-seen tool usage in non-sensitive environment,
- low-confidence signal with no risky action.

Expected response:
- log and monitor,
- no immediate escalation.

---

### S1 — Low
Definition:
- minor policy drift or medium uncertainty event with limited impact scope.

Examples:
- medium-confidence use in low-sensitivity repo,
- minor config drift without risky action execution.

Expected response:
- warning and routine review,
- no incident declaration.

---

### S2 — Medium
Definition:
- meaningful risk signal or policy deviation requiring active analyst attention.

Examples:
- risky action attempt in business-sensitive context,
- repeated warning patterns in same session,
- evidence ambiguity with potentially material impact.

Expected response:
- triage within defined window,
- approval/containment decisions as needed.

---

### S3 — High
Definition:
- high-confidence risky behavior affecting sensitive assets or indicating active policy breach.

Examples:
- unauthorized broad write activity in protected repo,
- disallowed command execution attempt with strong evidence,
- exception misuse with scope violation.

Expected response:
- rapid triage,
- containment and incident workflow initiation.

---

### S4 — Critical
Definition:
- confirmed or near-certain severe policy breach with high-impact potential/realization.

Examples:
- prohibited privileged action execution in restricted environment,
- high-confidence exfiltration path activation,
- repeated high-severity bypass behavior with active impact.

Expected response:
- immediate incident handling,
- leadership notification path,
- post-incident review mandatory.

---

## 3) Severity Determination Inputs
Severity should be computed from weighted factors:
1. **Action risk class** (R1-R4)
2. **Asset sensitivity tier** (Tier0-Tier3)
3. **Detection confidence**
4. **Actor trust posture**
5. **Policy decision outcome** (warn/approval/block/allowed)
6. **Recurrence pattern** (repeat attempts/escalation behavior)
7. **Evidence integrity quality**

Severity should never be based on one dimension alone.

---

## 4) Determination Model (Example)

Base severity seed:
- from action risk class + sensitivity tier.

Adjustments:
- increase severity if confidence is high and actor trust is low.
- increase severity for repeated violations or bypass attempts.
- downgrade only when confidence/evidence is demonstrably weak and impact low.

Hard floors:
- certain explicit-deny policy hits in Tier3 contexts cannot score below S3.

---

## 5) Severity-to-Response Mapping

### S0
- action: detect-only
- analyst SLA: backlog/periodic review
- reporting: aggregate trend only

### S1
- action: warn/monitor
- analyst SLA: routine queue
- reporting: include in weekly posture summary

### S2
- action: active triage + possible approval constraints
- analyst SLA: same business day (policy-defined)
- reporting: operational review queue

### S3
- action: containment-oriented response
- analyst SLA: rapid (hours)
- reporting: incident candidate + management visibility

### S4
- action: immediate incident response
- analyst SLA: urgent/immediate
- reporting: executive + incident command path

---

## 6) Severity and Enforcement Relationship
Severity is related to—but distinct from—enforcement state.

- A blocked event can still be S2 if impact was prevented and context limited.
- An allowed event can be S3 if policy gap enabled high-risk behavior.

Therefore, severity must account for **risk realized or narrowly averted**, not just final enforcement action.

---

## 7) Escalation and Recurrence Rules
- repeated S1/S2 events in same session/actor context can auto-escalate severity.
- repeated denied attempts should trigger severity step-up and potential incident flag.
- recurrence windows must be configurable (e.g., rolling 24h/7d).

---

## 8) Exception Interaction
Events allowed by exception still require severity scoring.

If exception scope is exceeded:
- severity escalates (typically S2+).

If exception is stale/expired and action proceeds attempt:
- severity escalates based on context and trust posture.

Exception usage should not mask true risk level.

---

## 9) Reporting Requirements
Severity taxonomy must support:
- event counts by severity and class,
- trend over release periods,
- hotspot analysis by tool/asset/team,
- recurrence and escalation patterns,
- SLA compliance by severity.

Buyer-safe reporting should include severity methodology summary and caveats.

---

## 10) Failure Modes and Safeguards

### Failure Mode: Severity inflation (alert fatigue)
Safeguard:
- calibration reviews and threshold tuning by empirical outcomes.

### Failure Mode: Severity suppression (missed risk)
Safeguard:
- hard floors for explicit high-risk conditions.

### Failure Mode: Inconsistent analyst interpretation
Safeguard:
- deterministic rule guidance + reason codes + examples.

### Failure Mode: Severity disconnected from SLA
Safeguard:
- enforce severity-to-SLA mapping in ops workflow tooling.

---

## 11) Validation Plan
1. run labeled scenario set through severity model.
2. compare assigned severities vs expected outcomes.
3. test recurrence-based escalations.
4. validate SLA routing behavior by severity.

Required artifacts:
- severity ruleset definition,
- scenario calibration results,
- escalation behavior report.

---

## 12) Buyer-Credibility Statement
"Our severity model is deterministic, context-aware, and tied to operational response SLAs. It reflects action risk, sensitivity, confidence, and recurrence so teams can prioritize effectively without guesswork."

---

## 13) Acceptance Checklist
- [x] Severity levels and definitions specified.
- [x] Determination inputs and mapping model documented.
- [x] Severity-to-response and SLA alignment defined.
- [x] Recurrence/exception interactions captured.
- [x] Failure safeguards and validation requirements defined.
- [ ] Empirical severity calibration evidence attached.
