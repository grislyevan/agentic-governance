# INIT-40 — ATT&CK-Style Tactics Mapping for Agent Misuse (Full Deep Revision)

## Scope
Issue: **INIT-40**
Objective: define a practical ATT&CK-style mapping model for agentic AI misuse patterns that links adversary-like behaviors to detection signals, policy controls, and response workflows.

This mapping should serve:
- threat modeling,
- SOC triage,
- control coverage analysis,
- buyer security diligence conversations.

---

## 1) Why ATT&CK-Style Mapping Is Needed
AI-agent misuse is often discussed abstractly, which makes controls hard to prioritize.

A tactic/technique mapping model translates abstract risk into:
- concrete behavior patterns,
- measurable detection goals,
- explicit control ownership,
- testable validation scenarios.

It creates a common language between product, security, and customer defenders.

---

## 2) Mapping Model Structure
Each mapping entry should include:
- `tactic_id`
- `tactic_name`
- `technique_id`
- `technique_name`
- `agentic_behavior_description`
- `primary_signal_layers[]`
- `required_controls[]`
- `detection_confidence_expectation`
- `response_playbook_ref`
- `test_scenarios[]`
- `coverage_status` (covered/partial/not-covered)

This schema keeps mapping actionable, not purely academic.

---

## 3) Proposed Tactic Families for Agent Misuse

### T1 — Discovery / Reconnaissance via Agent Context Access
Behavior examples:
- broad repository scanning,
- environment introspection,
- file/system inventory collection.

Detection anchors:
- high-volume read patterns,
- unusual directory traversal,
- command sequences focused on enumeration.

Controls:
- scope-limited reads,
- sensitive-path exposure controls,
- detection alerts for abnormal discovery patterns.

---

### T2 — Execution / Command Orchestration
Behavior examples:
- agent-driven shell/tool execution,
- chained command workflows,
- script generation and immediate execution.

Detection anchors:
- process lineage + command chain telemetry,
- privilege context,
- repeated plan/execute loops.

Controls:
- command class allow/deny,
- approval gating for privileged commands,
- block on prohibited execution patterns.

---

### T3 — Persistence / Workflow Implanting
Behavior examples:
- introducing scripts/tasks/configs that create recurring execution paths,
- modifying startup/build/deploy scripts to persist behavior.

Detection anchors:
- changes to startup/automation files,
- unusual cron/task/service modification behavior,
- repeat trigger conditions.

Controls:
- protected-file policies,
- change review requirements,
- high-severity escalation for persistence indicators.

---

### T4 — Privilege Abuse / Lateral Capability Expansion
Behavior examples:
- requesting or attempting elevated permissions,
- crossing intended scope boundaries (repo, host, environment).

Detection anchors:
- escalation command attempts,
- scope boundary violations,
- mismatch between actor trust tier and requested action class.

Controls:
- strict approval requirements,
- trust-tier constraints,
- deny-by-default for out-of-scope privileged paths.

---

### T5 — Collection / Sensitive Data Handling
Behavior examples:
- extraction or aggregation of sensitive source/config/credential material,
- packaging data for transfer.

Detection anchors:
- sensitive path access + aggregation patterns,
- high-risk file read/write combinations,
- context compression before outbound behavior.

Controls:
- sensitive data path policy,
- content-aware guardrails where available,
- stepped severity and incident flagging.

---

### T6 — Exfiltration / Unsanctioned Egress
Behavior examples:
- outbound transfers to unsanctioned destinations,
- proxy/gateway abuse to mask destination intent.

Detection anchors:
- network destination anomalies,
- process-to-egress correlation,
- transfer behavior after sensitive collection.

Controls:
- destination allowlists,
- egress restrictions by sensitivity tier,
- block and incident escalation for high-confidence cases.

---

### T7 — Impact / Integrity Disruption
Behavior examples:
- destructive modifications,
- broad overwrite/refactor in critical assets,
- policy-violating repository impact.

Detection anchors:
- high fan-out writes,
- risky command classes,
- protected-branch/policy bypass attempts.

Controls:
- branch and path protections,
- risk-based change-size gates,
- immediate block and incident response triggers.

---

## 4) Technique-to-Control Crosswalk Requirements
For each technique, map to:
1. detection signals by layer,
2. confidence expectations (low/med/high achievable contexts),
3. required policy controls,
4. enforcement ladder outcome targets,
5. severity expectations (INIT-38 linkage),
6. validation scenarios (INIT-28/29 linkage).

This crosswalk should identify where controls are absent or weak.

---

## 5) Coverage Scoring Model
Define coverage status per technique:
- **Covered**: detection + enforcement + evidence path validated.
- **Partial**: one or more pillars incomplete (e.g., detection only).
- **Not Covered**: no practical detection/enforcement path today.

Track additionally:
- confidence maturity,
- false positive/negative risk,
- mitigation roadmap status.

---

## 6) Operational SOC Integration
Mapping outputs should feed:
- triage runbooks,
- severity assignment guidance,
- incident response playbooks,
- hunt query libraries.

SOC use cases:
- quickly classify suspicious agentic events by tactic,
- prioritize alerts by impact path,
- identify recurring tactic patterns across teams/environments.

---

## 7) Threat-Informed Testing Linkage
Every mapped technique should have at least one replay/evasion scenario that exercises:
- expected signals,
- policy response,
- audit evidence quality.

Unmapped or untested techniques should be visible in risk backlog.

---

## 8) Failure Modes and Safeguards

### Failure Mode: Mapping is too generic to drive controls
Safeguard:
- require concrete behavior examples and control mappings for every technique.

### Failure Mode: Static mapping drifts from product capabilities
Safeguard:
- version mapping with release updates and deprecation notes.

### Failure Mode: Overstated coverage claims
Safeguard:
- coverage status must be evidence-backed and test-linked.

### Failure Mode: SOC cannot operationalize taxonomy
Safeguard:
- provide runbook and query references per technique.

---

## 9) Reporting Requirements
Produce regular outputs:
- tactic/technique coverage heatmap,
- uncovered or partial techniques by risk tier,
- mitigation progress for high-impact gaps,
- trend of tactic incidence over time.

Buyer-safe report subset should include:
- tested tactic classes,
- coverage posture,
- transparent limitations.

---

## 10) Validation Plan
1. create initial tactic/technique catalog for in-scope tool classes.
2. map each technique to existing controls and tests.
3. validate mapping with security architects and detection engineers.
4. run sample incident replay against mapping for practical utility.

Required artifacts:
- versioned mapping table,
- coverage heatmap,
- technique-to-test traceability report.

---

## 11) Buyer-Credibility Statement
"Our agentic AI threat model is mapped to ATT&CK-style tactics and techniques, with explicit links to detections, controls, and evidence-backed coverage status. This makes our security posture measurable and operational—not conceptual."

---

## 12) Acceptance Checklist
- [x] tactic families and behavior examples defined.
- [x] mapping schema and crosswalk requirements documented.
- [x] coverage scoring and SOC integration model specified.
- [x] testing linkage and failure safeguards captured.
- [x] reporting and validation requirements defined.
- [ ] initial mapped technique catalog and coverage evidence attached.
