# INIT-33 — One-Page Capability Brief (Full Deep Revision)

## Scope
Issue: **INIT-33**
Objective: define a high-impact, buyer-ready one-page brief that communicates product capability with technical honesty, clear differentiation, and evidence-backed credibility.

This artifact is not a marketing flyer. It is a compressed trust document that should survive first-pass scrutiny from:
- security buyers,
- technical evaluators,
- and economic decision-makers.

---

## 1) Purpose of the One-Pager
The one-pager should answer, within ~60 seconds:
1. What problem this product solves.
2. How it solves it differently.
3. What is proven today.
4. Where the limits are.
5. Why the buyer should trust the claims.

If it cannot do all five, it is not sales-ready.

---

## 2) Audience Segmentation and Message Priorities

### Primary audience: Security/IT decision owner
Needs:
- control outcomes,
- risk reduction confidence,
- implementation plausibility.

### Secondary audience: Security architect / detection engineer
Needs:
- signal model legitimacy,
- policy and audit semantics,
- limitation transparency.

### Tertiary audience: Economic buyer
Needs:
- operational value,
- risk posture improvement,
- defensible procurement narrative.

One-page copy should be readable by all three without contradiction.

---

## 3) Core Narrative Framework

### Problem statement
Agentic AI tooling introduces real endpoint risk because actions are executed through trusted developer environments, often bypassing simplistic app-name or network-only controls.

### Solution statement
The platform detects and governs AI tooling using a multi-signal model (process, file, network, identity, behavior) with confidence-scored, explainable policy outcomes.

### Outcome statement
Security teams gain practical control (detect/warn/approve/block), visibility into what happened and why, and defensible audit evidence.

---

## 4) Must-Have Sections (One-Page Layout)

### A) Headline + Value Proposition
Short, specific, non-hyped.
Example pattern:
"Govern agentic AI actions on endpoints with confidence-scored, explainable controls."

### B) What We Detect
- top supported tool classes,
- examples of covered tools,
- behavior-first detection framing.

### C) How We Decide
- confidence model summary,
- enforcement ladder summary,
- class-based policy model reference.

### D) What We Enforce
- risky action controls across shell/fs/network/repo,
- approval and exception controls,
- audit traceability.

### E) Proof and Validation
- benchmark/testing posture,
- evasion testing statement,
- evidence-backed claim posture.

### F) Known Limits (explicit)
- partial telemetry contexts,
- custom forks/wrappers caveat,
- localhost and proxy attribution boundaries.

### G) Call to Action
- scoped pilot proposal,
- what success criteria will be measured.

---

## 5) Claim Integrity Rules for This Artifact
Every claim on the one-pager must satisfy at least one:
1. directly measured in current benchmark data,
2. validated in replay/evasion suite,
3. explicitly labeled as roadmap/in-progress.

Disallowed claim patterns:
- "complete visibility" or "100% detection",
- unstated assumptions,
- capability implied from roadmap work.

---

## 6) Differentiation Positioning (Credible)

### Competitor contrast (without hype)
Many controls are app- or domain-centric. This product is behavior- and policy-centric, which is more resilient against renames, wrappers, and backend variability.

### Credibility anchor
Differentiation should be framed with measurable outcomes:
- confidence-calibrated decisions,
- policy outcome correctness,
- evasion resilience reporting,
- auditable evidence chain.

---

## 7) Visual Design Guidance
One-pager should include:
- compact architecture strip (signals → confidence → enforcement → audit),
- small capability matrix by tool class,
- mini decision ladder graphic,
- "Known Limits" box in equal visual weight (not hidden).

Design constraints:
- no dense tables unreadable in PDF print,
- no unexplained acronyms,
- high-contrast readability.

---

## 8) Buyer Objection Pre-Handling
One-pager should pre-answer common objections:
- "What about local models?" → local runtime controls and host telemetry.
- "What about forks/renamed tools?" → class-based, behavior-driven detection.
- "What about false blocks?" → confidence-aware ladder and approval path.
- "Can I audit decisions?" → rule ID + evidence-linked audit schema.

---

## 9) Failure Modes and Safeguards

### Failure Mode: Sounds good, says nothing concrete
Safeguard:
- enforce measurable capability bullets and proof references.

### Failure Mode: Overpromising breaks trust in technical review
Safeguard:
- mandatory known-limits section and claim linter.

### Failure Mode: One-pager disconnected from product reality
Safeguard:
- tie every section to current benchmark/report generator outputs.

### Failure Mode: Sales edits remove caveats
Safeguard:
- governance owner approval required for claim changes.

---

## 10) Build Workflow
1. pull latest validated benchmark outputs,
2. populate one-pager template with current metrics and limits,
3. run claim-integrity review,
4. security + product sign-off,
5. publish versioned PDF and source markdown.

Version metadata should include:
- release version,
- data snapshot date,
- approvers,
- claim lint pass status.

---

## 11) Validation Plan
- readability review by non-technical stakeholder,
- technical sanity review by detection engineer,
- objection simulation with security architect,
- alignment check against current benchmark report.

Required artifacts:
- one-page source file,
- approved PDF export,
- claim-to-evidence mapping checklist.

---

## 12) Buyer-Credibility Statement
"This one-page brief reflects validated capability and explicit limits. It is generated from the same evidence-backed framework used for engineering and security validation, so claims remain consistent from sales call to technical deep-dive."

---

## 13) Acceptance Checklist
- [x] Audience and narrative framework defined.
- [x] Required one-page sections specified.
- [x] Claim integrity and differentiation rules documented.
- [x] Objection handling and failure safeguards included.
- [x] Build and validation workflow specified.
- [ ] Final designed one-page artifact exported and approved.
