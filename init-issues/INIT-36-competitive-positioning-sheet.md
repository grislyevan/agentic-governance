# INIT-36 — Competitive Positioning Sheet (Full Deep Revision)

## Scope
Issue: **INIT-36**
Objective: define a technically honest, sales-usable competitive positioning sheet that differentiates the product on measurable capability, governance depth, and trustworthiness—without unverifiable claims.

This sheet should equip sales and technical teams to handle competitive comparisons with confidence and accuracy.

---

## 1) Why Competitive Positioning Needs Rigor
Security buyers increasingly test vendor claims in technical diligence sessions. Positioning that relies on vague superiority language fails quickly.

A credible positioning sheet must:
- map claims to evidence-backed capabilities,
- separate current-state from roadmap,
- identify where competitors may be stronger,
- and explain why your design choices matter operationally.

---

## 2) Positioning Philosophy

### Principle 1 — Capability-first, brand-second
Differentiate by outcomes and architecture patterns (multi-signal attribution, confidence-aware enforcement, auditability), not just competitor names.

### Principle 2 — Honest asymmetry
Acknowledge tradeoffs and known limits. Credibility increases when strengths and boundaries are both explicit.

### Principle 3 — Defensible language
Use terms tied to measurable behavior (decision accuracy, evasion resilience, evidence completeness), not hype terms.

---

## 3) Comparison Framework (Canonical)
All competitive comparisons should evaluate at least these dimensions:

1. **Detection Method**
   - signature/app-name, network-only, behavior-aware, multi-signal.
2. **Attribution Confidence Model**
   - binary/opaque vs calibrated confidence bands.
3. **Governance Controls**
   - visibility-only vs enforceable detect/warn/approve/block.
4. **Risky Action Control Depth**
   - whether shell/fs/network/repo controls are first-class.
5. **Exception and Approval Workflow**
   - ad hoc bypasses vs scoped, auditable workflows.
6. **Audit and Explainability**
   - event-only logs vs rule/evidence-linked decision traces.
7. **Evasion Resilience**
   - untested assumptions vs explicit adversarial testing.
8. **Operational Deployability**
   - endpoint realities (containers, proxies, local runtimes).
9. **Transparency of Limits**
   - hidden caveats vs published known gaps.

---

## 4) Core Differentiation Thesis

### Primary thesis
"We govern agentic AI actions with behavior- and risk-aware controls, not just tool name detection."

### Supporting pillars
- Multi-signal attribution improves reliability under real-world variability.
- Confidence-aware enforcement reduces both blind spots and unnecessary hard blocks.
- Risky action controls align security outcomes to actual business impact.
- Evidence-linked audit model supports technical and compliance scrutiny.
- Evasion testing plus honest gaps reporting increases trustworthiness.

---

## 5) Competitor Archetypes and Positioning Responses

### Archetype A — Signature/Inventory-Centric Tools
Strengths:
- easy deployment,
- quick app visibility.

Weaknesses:
- fragile under renames/wrappers,
- weak behavior and policy context.

Positioning response:
- emphasize resilience and decision quality over inventory counts.

### Archetype B — Network/CASB-Centric Controls
Strengths:
- strong for cloud egress oversight.

Weaknesses:
- weak for local runtime/localhost behaviors,
- limited endpoint action context.

Positioning response:
- highlight endpoint-first coverage for local and autonomous action paths.

### Archetype C — Assistive Coding-only Governance
Strengths:
- good IDE-native UX control.

Weaknesses:
- limited autonomous executor coverage,
- shallow risky action governance.

Positioning response:
- emphasize cross-class policy model including autonomous tool controls.

### Archetype D — SIEM-only Monitoring Pipelines
Strengths:
- strong aggregation/reporting.

Weaknesses:
- no direct enforcement and weak real-time control.

Positioning response:
- stress integrated decision + enforcement + audit loop.

---

## 6) Positioning Table Requirements
The actual sheet should include a matrix with rows for key capabilities and columns for:
- our platform,
- competitor archetype(s),
- evidence source.

Each row must include:
- capability definition,
- current support status,
- caveat notes,
- confidence level of claim.

No row should contain unverifiable competitor assertions.

---

## 7) Objection Handling Library (Required)

### Objection: "Everyone claims multi-signal"
Response:
- explain confidence calibration + decision trace outputs + evasion metrics.

### Objection: "Won’t this cause too many blocks?"
Response:
- confidence-aware ladder with step-up approvals before hard block in uncertain contexts.

### Objection: "Can you handle local models?"
Response:
- endpoint-local controls and model governance in class-based policy model.

### Objection: "How do we trust your claims?"
Response:
- benchmark/replay/evasion evidence + published known gaps.

---

## 8) Claim Safety Rules

Do:
- use measured language: "supported," "validated in X contexts," "known gaps include…"
- include caveats where scope is partial.

Do not:
- claim complete prevention,
- imply universal visibility,
- assert competitor limitations not validated by public evidence or direct test.

All comparative claims should reference evidence source categories:
- internal benchmark,
- public documentation,
- observed customer environment tests (sanitized).

---

## 9) Maintenance and Versioning
Positioning must be versioned with:
- product release version,
- benchmark dataset date,
- updated known-gaps snapshot,
- reviewer sign-off.

Refresh triggers:
- significant capability additions,
- major regression findings,
- material competitive landscape shifts.

---

## 10) Failure Modes and Safeguards

### Failure Mode: Overaggressive competitive claims
Safeguard:
- claim integrity review before publication.

### Failure Mode: Technical and sales narratives diverge
Safeguard:
- shared source-of-truth sheet tied to benchmark outputs.

### Failure Mode: Stale competitor assumptions
Safeguard:
- periodic review cadence and archived change logs.

### Failure Mode: Positioning ignores known limitations
Safeguard:
- mandatory linkage to Honest Gaps brief (INIT-34).

---

## 11) Validation Plan
1. technical review by detection/security architect.
2. sales usability review with live objection simulation.
3. claim-to-evidence mapping validation.
4. consistency check with one-pager and deep-dive appendix.

Required artifacts:
- versioned positioning sheet,
- objection handling addendum,
- claim integrity checklist.

---

## 12) Buyer-Credibility Statement
"Our competitive position is based on measurable control outcomes—detection reliability, enforcement quality, evasion resilience, and audit traceability—not generic feature checklists. We explicitly disclose limits and keep claims aligned with evidence."

---

## 13) Acceptance Checklist
- [x] Comparison framework and differentiation thesis defined.
- [x] Competitor archetype analysis documented.
- [x] Objection handling and claim safety rules specified.
- [x] Maintenance/versioning and safeguards defined.
- [x] Validation workflow and required artifacts listed.
- [ ] Final shareable positioning matrix produced and approved.
