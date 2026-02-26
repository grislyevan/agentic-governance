# INIT-15 — GitHub Copilot Detection Profile

## Scope
Tool: **GitHub Copilot** (IDE extension + account-linked AI assistance, including chat/agent-style workflows)
Goal: produce enterprise-usable detection and governance guidance with explicit confidence boundaries.

---

## 1) Tool Anatomy
Copilot behavior is tightly coupled to IDE extension state and GitHub identity context. It can appear as:
- inline suggestions/autocomplete,
- chat-assisted coding,
- broader agent-like workflows in supported IDEs.

Detection must distinguish **Copilot presence** from **Copilot-assisted behavior**.

---

## 2) 5-Layer Detection Model

### A) Process / Execution
Reliable signals:
- IDE host process (VS Code/JetBrains family) with Copilot extension active.
- Extension host subprocess activity tied to assistant interactions.
- Parent-child execution when Copilot workflows trigger terminal/tool actions.

Confidence:
- Medium when only IDE process is seen.
- High when extension-host + behavior sequence are correlated.

### B) File / Artifact
Reliable signals:
- Extension install manifests and version metadata.
- Workspace-level extension settings and policy files.
- Local logs/cache footprints indicating Copilot interaction windows.

Limitations:
- Artifact presence alone does not prove active Copilot use.

### C) Network
Reliable signals:
- GitHub/Copilot API endpoint communication patterns.
- Burst timing aligned with suggestion/chat activity.

Limitations:
- Shared enterprise proxies can blur attribution.
- Network-only cannot reliably separate autocomplete vs deeper assistant usage.

### D) Identity / Access
Reliable signals:
- GitHub account state tied to extension auth.
- Org-managed vs personal account context.
- License/entitlement context where available.

Policy-critical checks:
- Is Copilot usage from approved org account?
- Is repo under managed policy scope?

### E) Behavior
Reliable signals:
- Suggestion acceptance cadence + rapid edit bursts.
- AI-chat-to-edit sequences across multiple files.
- Adjacent terminal/commit actions following assistant interactions.

High-risk markers:
- Sensitive file/path interaction during active Copilot sessions.
- High-volume generated changes without normal review cadence.

---

## 3) What Works Well
1. Extension inventory + identity correlation strongly detects enabled/authorized Copilot usage.
2. Process/behavior correlation improves confidence for active assistance vs passive installation.
3. Repo/account policy checks provide direct governance value (not just observability).

---

## 4) What Doesn’t Work Reliably
1. Network-only attribution for Copilot mode classification.
2. Treating extension install as equivalent to active AI-assisted coding.
3. Single-signal controls in proxy-heavy or mixed-account environments.

---

## 5) Gaps & Evasion Conditions
1. Personal GitHub accounts on managed endpoints.
2. Remote dev containers where host telemetry is partial.
3. Extension forks/alternate clients mimicking Copilot-like flows.
4. Shared endpoints where user identity correlation is weak.

Mitigations:
- enforce org-account requirements,
- correlate IDE extension state + identity + behavior,
- apply confidence penalties when identity lineage is incomplete.

---

## 6) Confidence Rubric
- **High (>=0.75):** extension-host evidence + identity correlation + behavior sequence.
- **Medium (0.45–0.74):** two aligned layers without full identity or behavior certainty.
- **Low (<0.45):** isolated signal (endpoint-only or artifact-only).

---

## 7) Governance Mapping
- **Detect:** extension present/first-seen usage.
- **Warn:** medium-confidence usage in unapproved account/repo context.
- **Approval Required:** sensitive repository + high-assistance behavior patterns.
- **Block:** explicit policy violation (personal account in restricted repos, disallowed data boundaries).

---

## 8) Validation Plan
Positive scenarios (>=3):
1. Approved org account, normal coding suggestions.
2. Copilot chat-assisted multi-file edit flow.
3. Policy-compliant session with expected telemetry across all layers.

Evasion/failure scenarios (>=2):
1. Personal account session in managed endpoint.
2. Proxy-routed traffic with reduced endpoint attribution quality.

Required outputs:
- confidence score with rationale,
- evidence links (logs/screenshots/config snapshots),
- residual risk statement for partial-visibility scenarios.

---

## 9) Acceptance Checklist
- [x] Copilot-specific five-layer profile documented.
- [x] Mode/attribution limitations explicitly stated.
- [x] Identity/account governance logic mapped to enforcement.
- [x] Validation scenarios defined.
- [ ] Empirical lab evidence attached.
