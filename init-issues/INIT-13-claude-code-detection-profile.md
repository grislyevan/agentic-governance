# INIT-13 — Claude Code Detection Profile

## Scope
Tool: **Claude Code (CLI-based agentic coding workflow)**
Objective: Define practical endpoint detection + governance using current telemetry.

---

## 1) Signal Map (5-layer model)

### A. Process / Execution
**High-value detections**
- Executable invocation of Claude Code CLI (direct binary/package entrypoint).
- Parent-child chain: terminal → claude tool → spawned shell/git/node/python subprocesses.
- Repeated long-running interactive sessions tied to repo paths.

**Confidence**: High when combined with signer/path/args + parent lineage.

### B. File / Artifact
**High-value detections**
- Tool config files in user home and project directories.
- Session/history/cache artifacts created by Claude CLI workflows.
- Prompt/context helper files written near repo roots.

**Confidence**: Medium alone, High when paired with process evidence.

### C. Network
**High-value detections**
- TLS/SNI/hostname traffic to Anthropic/Claude API endpoints.
- Burst patterns matching prompt/response cycles during coding sessions.

**Confidence**: Medium alone (shared APIs/proxies can blur attribution).

### D. Identity / Access
**High-value detections**
- API key usage tied to user/device identity.
- Workspace/account correlation for org-vs-personal usage.

**Confidence**: Medium; strongest when mapped to process session IDs.

### E. Behavior
**High-value detections**
- Rapid code read/write loops across many files.
- Shell command orchestration from AI session context.
- Git commit/patch generation shortly after model interaction bursts.

**Confidence**: High for agentic activity class, Medium for tool-specific attribution.

---

## 2) What Works Well (Today)
1. **Process + behavior correlation** is the strongest practical signal.
2. **File artifacts** provide durable post-event evidence.
3. **Network metadata** helps confirm cloud-backed usage windows.
4. **Policy by class** (autonomous agent vs assistant) governs better than app-name blocklists.

---

## 3) What Does Not Work Reliably
1. **Domain-only blocking/detection** (easy to bypass via proxy/gateway).
2. **Single-signal attribution** (process-only or network-only creates false positives/negatives).
3. **Static binary name matching** (renaming/wrapping breaks naive signatures).

---

## 4) Known Gaps / Evasions
1. Renamed binaries and wrapper scripts.
2. Containerized/devcontainer/WSL execution reducing host visibility.
3. API traffic funneled through internal relay/proxy endpoints.
4. Shared model gateways obscuring “which tool” generated traffic.

---

## 5) Detection Confidence Rubric
- **High**: Process lineage + behavior + at least one of file/network/identity aligns.
- **Medium**: Two independent signals align but missing lineage or identity.
- **Low**: One weak signal only (e.g., endpoint/domain without local execution evidence).

---

## 6) Governance Mapping (Claude Code)
- **Detect**: First observation, low confidence, no sensitive repo access.
- **Warn**: Medium confidence + unapproved repo/workspace.
- **Approval required**: Shell/tool execution touching protected assets.
- **Block**: High confidence + explicit policy violation (sensitive data paths, disallowed commands, exfil patterns).

---

## 7) Test Cases to Track in Sprint
### Positive detections (target >=3)
1. Standard CLI usage in allowed repo.
2. Multi-file refactor session + git commit generation.
3. CLI session with shell tool usage.

### Evasion/failure tests (target >=2)
1. Renamed binary/wrapper invocation.
2. Proxy-routed API traffic with non-standard endpoint visibility.

---

## 8) Acceptance Checklist (INIT-13)
- [x] 5-layer detection profile documented.
- [x] Works / doesn’t / gaps explicitly captured.
- [x] Confidence rubric defined.
- [x] Governance action mapping defined.
- [x] Test matrix entries defined for validation run.
- [ ] Lab evidence artifacts linked (pending test execution).

---

## 9) Sales-Credibility Narrative Snippet
"Claude Code detection is reliable when correlated across execution, behavior, and identity signals. We do not claim perfect single-signal attribution; instead, we provide confidence-scored, explainable evidence with clear policy outcomes."
