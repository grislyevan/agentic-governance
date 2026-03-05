# LAB-RUN-013 Results: OpenClaw with Local LLM (Qwen 3.5 via Ollama)

**Run ID:** LAB-RUN-013  
**Date:** 2026-03-05  
**Tool:** OpenClaw v2026.3.1 (`openclaw` npm package)  
**Model Backend:** Qwen 3.5 0.8B via Ollama (`ollama/qwen3.5:0.8b`, localhost:11434)  
**Scenario ID:** OC-POS-05 (Same protocol as OC-POS-01 with local LLM backend)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/openclaw-lab/LAB-RUN-013/` (90 files, SHA-256 hashed per phase)  
**Comparison Run:** LAB-RUN-007 (OC-POS-01, same protocol, cloud LLM: gpt-5.3-codex via OpenAI)

> **Purpose:** Validate whether switching from a cloud LLM to a local LLM changes the detection profile. The hypothesis is that process, file, and identity IOCs remain identical while network and behavior IOCs change materially.

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.11) | Status | Evidence | LAB-RUN-007 Δ |
|---|---|---|---|
| `openclaw` CLI binary and `openclaw-gateway` daemon process | **Observed** | `phase2-onboard/openclaw-processes.txt` | **Identical.** Gateway PID 67171, same named process. Parent chain: `launchd (PID 1)` → `openclaw-gateway`. |
| Child process chains: gateway → shell → commands | **Not observed** | `phase3b-agentic/agentic-task-output.txt` | **Different.** 0.8B model failed to execute shell commands. No child processes spawned. In LAB-RUN-007 (gpt-5.3-codex), 3 files were created and pytest was attempted. |
| Persistent daemon (LaunchAgent on macOS) | **Observed** | `phase2-onboard/openclaw-plist-contents.txt` | **Identical.** `KeepAlive: true` + `RunAtLoad: true`. Same plist at `~/Library/LaunchAgents/ai.openclaw.gateway.plist`. |
| Cron/scheduled task execution | **Architecture confirmed, not exercised** | `phase3d-proactive/cron-state.txt` | **Identical.** Empty cron jobs list. Heartbeat: 30m. |

**Layer signal strength: 0.85** (down from 0.90 in LAB-RUN-007 — named daemon confirmed but no child process chains observed due to model limitation)

### File / Artifact Layer

| IOC (Playbook Section 4.11) | Status | Evidence | LAB-RUN-007 Δ |
|---|---|---|---|
| `~/.openclaw/` global config/state directory | **Observed** | `phase1-install/openclaw-dir-post.txt`, `phase4-teardown/openclaw-disk-final.txt` | **Identical.** 216 MB total disk footprint (vs 215 MB in LAB-RUN-007 — marginal growth from new session data). |
| `~/.openclaw/openclaw.json` central config | **Observed** | `phase2-onboard/openclaw-config.txt` | **Different content.** `agents.defaults.model.primary` is now `ollama/qwen3.5:0.8b` (was `gpt-5.3-codex`). Only provider configured is `ollama` with `baseUrl: http://localhost:11434`. Cloud auth profiles (Anthropic, Google, OpenAI-Codex) still present in `auth.profiles` but not active for inference. |
| Skills directory with self-authored skills | **Observed (pre-existing)** | `phase3c-selfmod/skills-before.txt`, `phase3c-selfmod/skills-diff.txt` | **Same artifact, different behavior.** `temperature-converter/SKILL.md` from LAB-RUN-007 still present. Qwen 3.5 attempted to create a new skill but **failed** — the 0.8B model could not complete the skill authoring task. No new skills created in this run. |
| Credentials directory | **Observed** | `phase2-onboard/credentials-dir.txt` | **Identical.** WhatsApp channel credentials present. |
| Session/conversation persistence | **Observed** | `phase3a-basic/agents-state-post.txt` | **Identical structure.** 4 sessions, default model now `qwen3.5:0.8b`. Older Slack sessions still reference `gpt-5.3-codex`. |
| LaunchAgent plist | **Observed** | `phase2-onboard/openclaw-plist-contents.txt`, `phase4-teardown/launch-agents-final.txt` | **Identical.** Persists after gateway stop. Embedded credentials (JIRA, gateway token) unchanged. |
| Workspace prompt files (AGENTS.md, SOUL.md, TOOLS.md) | **Observed** | `phase2-onboard/workspace-prompt-files.txt` | **Identical.** |

**Layer signal strength: 0.95** (identical to LAB-RUN-007 — the file footprint is model-independent)

### Network Layer

| IOC (Playbook Section 4.11) | Status | Evidence | LAB-RUN-007 Δ |
|---|---|---|---|
| Gateway WS listener on `:18789` | **Observed** | `phase2-onboard/port-18789-at-onboard.txt`, `phase3a-basic/port-18789-during-task.txt` | **Identical.** `node` (PID 67171) listening on `localhost:18789` (IPv4 + IPv6). Process-to-socket attribution is clean. |
| Model provider API traffic | **Different — LOCAL** | `phase3a-basic/outbound-during-task.txt` | **KEY DIFFERENCE.** Model inference traffic is now `127.0.0.1:* → 127.0.0.1:11434` (Ollama). No outbound :443 traffic to `api.openai.com` or `api.anthropic.com` for inference. However, gateway (PID 67171) still maintains ONE outbound :443 connection to `57.144.105.32:443` — likely telemetry, update checks, or WhatsApp channel keepalive. |
| Ollama local model server | **Observed (NEW IOC)** | `phase2-onboard/port-11434-at-onboard.txt`, `phase3a-basic/port-11434-during-task.txt` | **New in this run.** Ollama PID 26237 listening on `localhost:11434`. During inference, Ollama spawns a worker process (PID 97338) with loopback connections. The gateway-to-Ollama connection is entirely local. |
| Chat platform connections | **Config confirmed, not exercised** | `phase2-onboard/openclaw-status.txt` | **Identical.** WhatsApp linked, Slack configured. |

**Layer signal strength: 0.65** (down from 0.70 in LAB-RUN-007 — gateway listener confirmed, but inference traffic is local-only, reducing the network signal's forensic value for model attribution)

### Identity / Access Layer

| IOC (Playbook Section 4.11) | Status | Evidence | LAB-RUN-007 Δ |
|---|---|---|---|
| Model provider API keys in config/env | **Observed** | `phase2-onboard/openclaw-config.txt`, `baseline/ai-env.txt` | **Partially different.** Cloud auth profiles still exist in config but active model uses `ollama-local` API key (a placeholder — Ollama requires no real auth). `OPENAI_API_KEY` still present in environment. |
| Chat platform credentials in config | **Observed** | `phase2-onboard/openclaw-plist-contents.txt` | **Identical.** LaunchAgent plist embeds JIRA_API_TOKEN, JIRA_EMAIL, OPENCLAW_GATEWAY_TOKEN. |
| OS user running daemon | **Observed** | `phase2-onboard/openclaw-processes.txt` | **Identical.** Daemon runs as user `echance`. |

**Layer signal strength: 0.80** (slightly down from 0.85 in LAB-RUN-007 — active model uses a placeholder API key, reducing the identity signal from the model provider dimension)

### Behavior Layer

| IOC (Playbook Section 4.11) | Status | Evidence | LAB-RUN-007 Δ |
|---|---|---|---|
| Shell command execution from agent context | **FAILED** | `phase3b-agentic/agentic-task-output.txt`, `phase3b-agentic/agentic-task-output-retry.txt` | **KEY DIFFERENCE.** The 0.8B model could not complete agentic tasks. First attempt: "Ollama API stream ended without a final response". Second attempt: model tried to write to wrong path (`~/.openclaw/workspace/hello-world/hello.py` instead of `~/openclaw-lab-workspace/`) and the write failed. No files created in workspace. In LAB-RUN-007, gpt-5.3-codex created 3 files and attempted pytest. |
| Self-modification (skill authoring + hot-reload) | **FAILED** | `phase3c-selfmod/skill-creation-output.txt`, `phase3c-selfmod/skills-diff.txt` | **KEY DIFFERENCE.** The 0.8B model failed to create a new skill. "Ollama API stream ended without a final response" followed by a failed read of a nonexistent skill path. No new skills created. In LAB-RUN-007, gpt-5.3-codex successfully created `temperature-converter/SKILL.md`. |
| Simple Q&A from agent context | **Observed** | `phase3a-basic/basic-interaction-output.txt` | **Same capability.** Model correctly answered "Paris is the capital of France." Response quality is adequate for simple retrieval but no tool use was exercised. |
| Proactive/scheduled execution | **Architecture confirmed, not exercised** | `phase3d-proactive/cron-state.txt`, `phase3d-proactive/cron-capabilities.txt` | **Identical.** Cron infrastructure exists but no jobs configured. Model failed to describe cron capabilities (API stream ended). |

**Layer signal strength: 0.40** (down from 0.80 in LAB-RUN-007 — the 0.8B model demonstrated only simple Q&A; all tool-use, shell execution, and self-modification behaviors failed)

---

## 2. Confidence Score Calculation

### Using OpenClaw Calibrated Weights (LAB-RUN-007 / Appendix B)

```
Layer                Weight    Signal Strength    Weighted     LAB-007
Process / Execution  0.25      0.85               0.2125       0.225
File / Artifact      0.30      0.95               0.285        0.285
Network              0.15      0.65               0.0975       0.105
Identity / Access    0.15      0.80               0.120        0.1275
Behavior             0.15      0.40               0.060        0.120
                                          ──────────────
base_score                                         0.775
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (daemon chain clear)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard npm install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.openclaw/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct connection)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Model inference traffic is local-only; gateway :443 connection not attributable to model)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[✗] Weak/missing identity correlation:           −0.10  → NOT APPLIED (strong identity layer)
                                                 ──────
penalties                                         0.05
```

### Final Score

```
final_confidence = 0.775 - 0.05 = 0.725

Classification: Medium (0.45–0.74)

LAB-RUN-007 comparison: 0.80 (High) → 0.725 (Medium)
Delta: −0.075 (dropped from High to Medium)
```

### Score Assessment

The drop from High (0.80) to Medium (0.725) is **driven entirely by the behavior layer**. The 0.8B model's inability to perform tool-use tasks means the behavior signal dropped from 0.80 to 0.40. This is a critical finding:

**The detection confidence of an agentic tool is partially dependent on the model's capability.** A small, incapable model reduces the *behavioral risk* but also reduces *behavioral detectability*. The process, file, identity, and persistence IOCs remain model-independent — the tool's infrastructure is just as detectable regardless of the model.

**Using default five-layer weights:**

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.85               0.255
File / Artifact      0.20      0.95               0.190
Network              0.15      0.65               0.0975
Identity / Access    0.15      0.80               0.120
Behavior             0.20      0.40               0.080
                                          ──────────────
base_score                                         0.7425
penalties                                          0.05
final_confidence                                   0.6925

Classification: Medium (0.45–0.74)
```

Under default weights, the score also falls to Medium (0.69). The behavioral penalty is amplified because default weights give behavior 0.20 vs the calibrated 0.15.

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value | LAB-RUN-007 |
|---|---|---|
| Detection Confidence | Medium (0.725) | High (0.80) |
| Tool Class | C (persistent daemon) | C (persistent daemon) |
| Asset Sensitivity | Tier 0 | Tier 0 |
| Action Risk | R2 (daemon + persistence) | R3 (shell execution + self-modification) |
| Actor Trust | T2 | T2 |

**Applicable rules:**
- Rule 2: Medium confidence + Class C → **Approval Required**
- Rule 5: Persistent daemon → **Approval Required at minimum**
- Rule 3: Would trigger at R3, but **R3 is not applicable** — the model couldn't execute shell commands

**Decision: Approval Required** (same as LAB-RUN-007, but at lower confidence and lower action risk)

**Key governance insight:** The policy outcome is the same (Approval Required) because the tool's infrastructure characteristics (Class C, persistent daemon) drive the policy decision, not the model's capability. A small model in an unrestricted daemon is still a governance concern — the tool *could* execute shell commands if a more capable model were swapped in.

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-013
Date:                2026-03-05
Tool:                OpenClaw v2026.3.1 (npm package, Node.js)
Model Backend:       Qwen 3.5 0.8B via Ollama (localhost:11434)
Scenario ID:         OC-POS-05 (Same as OC-POS-01 with local LLM)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — openclaw-gateway daemon (PID 67171) with clean
                     launchd parent chain. Named process, easily identifiable.
                     LaunchAgent with KeepAlive + RunAtLoad. No child process
                     chains (model too small for tool use).
                     Evidence: phase2-onboard/openclaw-processes.txt
  File/Artifact:     OBSERVED — ~/.openclaw/ with 216 MB. Config, credentials,
                     sessions, skills (pre-existing), logs, memory, workspace.
                     Config now points to ollama/qwen3.5:0.8b.
                     Evidence: phase1-install/openclaw-dir-post.txt,
                     phase2-onboard/openclaw-config.txt
  Network:           OBSERVED — Gateway WS listener on localhost:18789. Model
                     inference traffic is LOCAL (127.0.0.1 → 127.0.0.1:11434).
                     One outbound :443 connection from gateway (telemetry/
                     channel keepalive, not model inference).
                     Evidence: phase3a-basic/outbound-during-task.txt,
                     phase3a-basic/port-11434-during-task.txt
  Identity:          OBSERVED — Plist credentials (JIRA, gateway token).
                     OPENAI_API_KEY in env. Active model uses placeholder key
                     ("ollama-local"). Cloud auth profiles dormant but present.
                     Evidence: phase2-onboard/openclaw-plist-contents.txt,
                     baseline/ai-env.txt
  Behavior:          PARTIALLY OBSERVED — Simple Q&A succeeded (Paris).
                     ALL tool-use tasks FAILED: shell execution, file creation,
                     skill authoring, cron description. The 0.8B model is not
                     capable enough for agentic behavior.
                     Evidence: phase3a-basic/basic-interaction-output.txt,
                     phase3b-agentic/agentic-task-output.txt

Confidence Result:   0.725 (Medium) — calibrated weights
                     0.6925 (Medium) — default weights
                     LAB-RUN-007 comparison: 0.80 (High), delta: −0.075
Policy Decision:     Approval Required (Rule 2 + Rule 5)
Evidence Links:      90 files across 8 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Model could be swapped to a capable model at any time
                     (config change only); behavioral risk is latent, not absent.
                     Chat platform connections not tested. Browser not tested.
```

---

## 5. LAB-RUN-007 vs LAB-RUN-013 Comparison

| Dimension | LAB-RUN-007 (Cloud LLM) | LAB-RUN-013 (Local LLM) | Assessment |
|---|---|---|---|
| **Model** | gpt-5.3-codex (OpenAI, cloud) | qwen3.5:0.8b (Ollama, local) | Different provider, different capability |
| **Model inference traffic** | Outbound :443 to OpenAI API | Local 127.0.0.1:11434 (Ollama) | Network IOC fundamentally changed |
| **Outbound :443 from gateway** | Present (model API) | **Still present** (telemetry/channel) | Gateway makes outbound connections even with local model |
| **Process IOCs** | Confirmed (daemon + child chains) | Confirmed (daemon only — no child chains) | Model capability affects child process spawning |
| **File IOCs** | Confirmed (215 MB) | Confirmed (216 MB) | Model-independent |
| **Identity IOCs** | Confirmed (API keys, plist creds) | Confirmed (plist creds, placeholder model key) | Slightly different: active model key is a placeholder |
| **Shell execution** | Confirmed (3 files + pytest) | **Failed** (0.8B model too small) | Model capability directly affects behavioral IOCs |
| **Self-modification** | Confirmed (temperature-converter skill) | **Failed** (0.8B model too small) | Model capability directly affects behavioral IOCs |
| **Simple Q&A** | Confirmed | Confirmed | Both models handle simple retrieval |
| **Confidence score** | 0.80 (High) | 0.725 (Medium) | −0.075 delta, driven by behavior layer |
| **Policy decision** | Approval Required / Block | Approval Required | Same floor (daemon persistence), lower ceiling |
| **Ollama co-residency** | Not applicable | Ollama PID 26237 on :11434 | New detection surface: OpenClaw + Ollama symbiosis |
| **Security audit** | 2 CRITICAL, 2 WARN | 3 CRITICAL, 2 WARN, 1 INFO | New: "Small models require sandboxing" — OpenClaw's own audit flags the 0.8B model as unsafe |

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **Model capability directly affects behavioral detection confidence.** The 0.8B Qwen model could not perform tool use, shell execution, or self-modification. Behavioral IOCs that depend on agentic execution are only detectable when the model is capable enough. This creates a detection gap: a small model reduces behavioral *risk* but also reduces behavioral *observability*. | Section 4.11 Behavior IOC, Appendix B | Add note: behavioral signal strength is partially model-dependent. Small models (< ~3B params) may not trigger tool-use IOCs. Detection should not rely solely on observed behavior — infrastructure IOCs (process, file, persistence) are model-independent and should be weighted as primary anchors. |
| 2 | **Local LLM eliminates outbound model API traffic but does NOT eliminate all outbound connections.** The gateway still maintains a :443 connection (telemetry/channel keepalive) even with a fully local model backend. Network detection cannot assume "local model = no outbound traffic". | Section 4.11 Network IOC | Add IOC variant: "With local model backend, inference traffic is localhost-only (e.g., :11434). Gateway may still make outbound :443 connections for telemetry, update checks, or channel keepalive. Absence of model API traffic does NOT equal absence of network signals." |
| 3 | **OpenClaw + Ollama co-residency creates a new detection pattern.** When OpenClaw uses Ollama as its backend, both tools are simultaneously present: gateway on :18789, Ollama on :11434, with loopback connections between them. Detection should check for this symbiotic relationship. | Section 4.11 Network IOC, Section 4.4 (Ollama) | Add cross-reference: "OpenClaw may use Ollama as a local model backend. When co-resident, the gateway process connects to localhost:11434 for inference. Detection of Ollama + OpenClaw together indicates a local autonomous agent configuration." |
| 4 | **OpenClaw's own security audit flags small models as unsafe.** `openclaw status` reports "CRITICAL: Small models require sandboxing and web tools disabled" for the 0.8B model. The tool's built-in security diagnostics can be leveraged as a governance signal — a CRITICAL audit finding from the tool itself corroborates governance risk classification. | Section 4.11 (new), Section 11 | Add IOC: "`openclaw status` security audit findings. CRITICAL-level findings (e.g., small model without sandboxing, open group policy) are governance-relevant signals that the tool's own security model has identified risk." |
| 5 | **Confidence scoring should have a floor for infrastructure-class tools.** The behavioral layer dropped to 0.40 because the model couldn't perform agentic tasks. But the tool *can* perform agentic tasks if the model is swapped — the capability is latent. A confidence floor based on infrastructure IOCs (process + file + persistence) would prevent underscoring tools with capable infrastructure but temporarily incapable models. | Appendix B | Consider a confidence floor for Class C/D tools with persistent daemon infrastructure: if process + file layers both score ≥ 0.80, the final confidence should not drop below 0.70 regardless of behavior layer. This prevents a model swap from creating a detection blind spot. |
| 6 | **Model swap is a config-only change with no approval gate.** Changing the model from gpt-5.3-codex to qwen3.5:0.8b (or vice versa) requires only editing `openclaw.json`. There is no approval mechanism, audit trail beyond config backups, or notification. A user could swap from a small, incapable model to a large, fully agentic model in seconds. | Section 4.11 Behavior IOC, Section 7 | Add governance recommendation: model configuration changes in persistent agentic tools should trigger alerts. The config backup chain (`openclaw.json.bak.*`) enables forensic detection of model swaps after the fact. |
| 7 | **The write-to-wrong-path failure reveals the 0.8B model's imprecise tool use.** When the small model attempted agentic execution, it targeted `~/.openclaw/workspace/hello-world/hello.py` instead of the requested `~/openclaw-lab-workspace/hello.py`. This misdirection is itself a risk signal: an imprecise model with tool access may write to unintended locations. | Section 7 (Risky Action Controls) | Note that small models with tool access may execute imprecisely, creating unintended file system modifications. OpenClaw's exec-approvals mechanism provides some protection, but path validation is model-dependent. |

---

## 7. Proposed Weight Adjustment for Local-LLM Configuration

For OpenClaw with a local LLM backend, the calibrated weights from LAB-RUN-007 remain appropriate. The behavioral weight (0.15) is already the lowest, which correctly de-emphasizes the behavior layer when the model is incapable. No weight change is recommended.

However, the finding about confidence floors (Finding #5) suggests a structural change to the scoring formula rather than weight adjustments.

---

## 8. Summary

LAB-RUN-013 confirms the hypothesis: **switching from a cloud LLM to a local LLM changes the network and behavior IOCs but leaves the process, file, identity, and persistence IOCs unchanged.**

**What stayed the same:**
- Process layer: gateway daemon, LaunchAgent with KeepAlive + RunAtLoad
- File layer: 216 MB `~/.openclaw/` directory with full config/credential/session footprint
- Identity layer: plist-embedded credentials, environment API keys
- Persistence: LaunchAgent plist survives gateway stop
- Policy decision: Approval Required (driven by infrastructure, not model)

**What changed:**
- Network layer: model inference traffic is local (127.0.0.1:11434) instead of outbound :443. Gateway still makes one outbound :443 connection (telemetry/channel).
- Behavior layer: 0.8B model failed ALL tool-use tasks (shell execution, file creation, skill authoring). Simple Q&A succeeded. Behavioral risk is *latent* but not *absent* — a config-only model swap would restore full agentic capability.
- Confidence: 0.725 (Medium) vs 0.80 (High) — a 0.075 drop driven entirely by the behavior layer.
- New co-residency pattern: OpenClaw + Ollama running together, with loopback connections between gateway (:18789) and model server (:11434).

**Key governance takeaway:** Detection strategies must not rely on behavioral IOCs alone. Infrastructure-based detection (process, file, persistence, network listeners) is model-independent and provides a stable detection foundation regardless of which model — or how capable a model — is configured. The capability to perform agentic tasks is a property of the tool's infrastructure, not the current model assignment.
