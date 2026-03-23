# INIT-14 — Cursor Detection Profile

## Scope
Tool: **Cursor** (desktop IDE with embedded AI assistant/agent workflows)
Goal: establish reliable, explainable detection + governance patterns suitable for enterprise endpoint security.

---

## 1) Tool Anatomy (why Cursor is different)
Cursor is not just a chatbot app; it is an IDE environment with deeply integrated AI actions:
- inline edits and code generation
- multi-file refactors
- repo-aware context ingestion
- terminal/shell invocation from development workflows

That means detection must separate:
1. normal developer IDE behavior,
2. AI-assisted editing,
3. high-risk agentic behavior (autonomous-like orchestration).

---

## 2) Detection Model by Telemetry Layer

### A) Process / Execution
**Reliable indicators**
- Signed Cursor app process execution from known install paths.
- Child process lineage from Cursor/embedded terminals to shell/tool execution.
- Repeated session patterns where Cursor remains active while child process and file write bursts occur.

**Collection targets**
- process name/path/hash/signer
- parent-child tree depth
- command-line digest for spawned shells/tools
- execution session duration

**Confidence**
- High when process lineage + child execution chain are present.
- Medium when only top-level process exists without behavioral corroboration.

---

### B) File / Artifact
**Reliable indicators**
- Cursor-specific settings/workspace artifacts in user config directories.
- IDE extension/plugin state files and local caches tied to AI feature usage.
- Burst edits across repo files with consistent timing signatures.

**Collection targets**
- settings/config paths (per user + workspace)
- cache/session files (timestamps + hashes)
- changed file fan-out per time window

**Confidence**
- Medium alone (IDEs can look similar), High with process + behavior correlation.

---

### C) Network
**Reliable indicators**
- TLS/SNI metadata to Cursor/cloud-model infrastructure (where applicable).
- Request burst patterns aligned with prompt-response editing cycles.

**Known limitations**
- Shared enterprise proxies or model gateways reduce direct attribution quality.
- Network-only detection cannot reliably distinguish Cursor from other IDE+LLM flows.

**Confidence**
- Medium with endpoint metadata only.
- High only when correlated to local process identity and timing.

---

### D) Identity / Access
**Reliable indicators**
- Mapped user identity on endpoint session + IDE account state.
- Corporate vs personal account context for policy enforcement.

**Policy-critical checks**
- Is user on managed endpoint?
- Is account corporate-approved?
- Is repo/workspace within approved boundary?

**Confidence**
- Medium by itself, high in combination with process and workspace context.

---

### E) Behavior
**Reliable indicators**
- High-frequency multi-file edit loops after prompt-like interaction cadence.
- Context-heavy reads + concentrated writes (agentic edit shape).
- Shell invocations proximate to AI edit sequences.

**High-risk patterns**
- Sensitive path touches + outbound egress in same session.
- Automated patch/commit generation without normal review cadence.

**Confidence**
- High for classifying agentic-like behavior when temporal sequencing is preserved.

---

## 3) What Works (Today)
1. **Process + behavior fusion** is the strongest practical signal.
2. **Artifact persistence** provides durable forensic and customer-proof evidence.
3. **Identity + repo boundary checks** support actionable governance (not just visibility).

---

## 4) What Doesn’t Work Reliably
1. **Network-only attribution** in proxy-heavy environments.
2. **Static app-name signatures** without lineage and behavior context.
3. **Single-signal policy decisions** (too noisy for enterprise reliability).

---

## 5) Evasion / Blind Spot Analysis
1. Portable installs and non-standard launch wrappers.
2. Containerized/remote development sessions reducing host-native visibility.
3. Shared model endpoints masking tool-specific attribution.
4. Forked/customized builds altering expected artifacts.

Mitigation strategy:
- score-based multi-signal attribution,
- explicit confidence penalties for missing telemetry,
- policy escalation only when confidence + sensitivity thresholds are met.

---

## 6) Confidence Rubric (Cursor)
- **High (>=0.75):** Cursor process lineage + behavioral sequence + one supporting layer (file/network/identity).
- **Medium (0.45–0.74):** two layers align but lacking lineage or identity certainty.
- **Low (<0.45):** isolated signal only (e.g., endpoint/domain hit with no local corroboration).

---

## 7) Governance Mapping for Cursor
- **Detect:** first-seen use, low-confidence events, managed endpoint baseline.
- **Warn:** medium-confidence use in unapproved repo/account context.
- **Approval Required:** sensitive repository, privileged shell actions, cross-boundary data movement.
- **Block:** high-confidence violation involving prohibited data zones or explicit control bypass.

---

## 8) Validation Plan (Issue Acceptance)

### Positive scenarios (minimum 3)
1. Standard Cursor editing session in approved repo.
2. Multi-file AI-assisted refactor with expected process/file/behavior signals.
3. Cursor + terminal-assisted workflow with policy-compliant command chain.

### Evasion/failure scenarios (minimum 2)
1. Wrapped/renamed launch path to test process-signature robustness.
2. Proxy-routed network path to test attribution degradation handling.

### Required outputs
- confidence outcome and rationale for each run,
- evidence links (logs/screenshots/hash references),
- residual risk statement where coverage is partial.

---

## 9) Acceptance Criteria for INIT-14
- [x] Cursor-specific 5-layer detection profile documented.
- [x] Works / doesn’t / gaps captured without boilerplate generalization.
- [x] Confidence scoring mapped to enforceable policy actions.
- [x] Validation scenarios defined for lab execution.
- [ ] Empirical lab evidence attached (pending run execution).

---

## 10) Buyer-Facing Credibility Statement
"Cursor detection is reliable when endpoint execution lineage and behavioral telemetry are correlated with identity and network context. We avoid overclaiming network-only attribution and provide confidence-scored, explainable enforcement decisions."
