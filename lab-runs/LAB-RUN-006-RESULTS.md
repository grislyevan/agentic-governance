# LAB-RUN-006 Results: Open Interpreter Installation & Runtime Telemetry

**Run ID:** LAB-RUN-006  
**Date:** 2026-03-02  
**Tool:** Open Interpreter v0.4.3 (`open-interpreter` pip package)  
**Scenario ID:** OI-POS-01 (Standard venv install + agentic command execution with direct shell access)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/oi-lab/LAB-RUN-006/` (78 files, SHA-256 hashed per phase)  
**Model Backend:** Ollama local (llama3.2:1b) — fallback from OpenAI (quota exceeded)

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.7) | Status | Evidence | Notes |
|---|---|---|---|
| Python runtime mapped to Open Interpreter entrypoints/modules | **Observed** | `phase1-install/binary-metadata.txt`, `phase1-install/which-interpreter.txt` | Entrypoint at `~/oi-lab-venv/bin/interpreter` — a Python script (276 bytes) importing `interpreter.terminal_interface.start_terminal_interface`. Process appears as `python3` in `ps`, NOT as `interpreter`. This is a critical detection difference from Claude Code — the process name does not reveal the tool identity. Detection must match Python processes with `interpreter` module paths in their arguments or link to the venv `bin/interpreter` entrypoint. |
| Parent lineage: terminal/script → open-interpreter → child command chains | **Observed** | `phase3-agentic/python-process-stream.txt`, `phase3-agentic/agentic-session-output.txt` | Process chain: `zsh` → `python3` (running interpreter) → `ipykernel` (Jupyter kernel for code execution) → `bash` (shell commands) → `pip`/`pytest`/`cat`. Open Interpreter uses Jupyter/IPyKernel as its code execution substrate — this is a significant architectural finding not mentioned in the playbook. The child command chain is mediated through a Jupyter kernel, not direct subprocess calls. |
| Privilege context: effective uid/admin elevation during sessions | **Observed (no escalation)** | `phase2-launch/privilege-context.txt`, `phase3-agentic/privilege-escalation-check.txt` | Running as user `echance` (uid=503) with `admin` group membership. No `sudo` invocations detected during the agentic session. The tool did NOT attempt privilege escalation for the scoped task. However, with `auto_run=True`, nothing prevents it from running `sudo` if the model generates such a command — the safety boundary is entirely LLM-dependent. |

**Layer signal strength: 0.70** (Process identification is weaker than Claude Code — generic `python3` process name requires deeper argument/module inspection. Jupyter kernel mediation adds indirection. Parent chain confirmed but requires knowledge of the IPyKernel architecture.)

### File / Artifact Layer

| IOC (Playbook Section 4.7) | Status | Evidence | Notes |
|---|---|---|---|
| `open-interpreter` package in venv/site-packages | **Observed** | `phase1-install/interpreter-package-contents.txt`, `phase1-install/pip-show-oi.txt` | Package at `~/oi-lab-venv/lib/python3.11/site-packages/interpreter/`. 135+ dependencies installed (583 MB venv). Package metadata: Author "Killian Lucas", email `killian@openinterpreter.com`. Key subpackages: `core/`, `terminal_interface/`, `computer/`. The package footprint is contained entirely within the venv. |
| Session history/transcript artifacts | **Not observed** | `phase4-teardown/oi-config-final.txt`, `phase4-teardown/oi-artifacts-final.txt` | **No persistent session artifacts found.** No `~/.config/open-interpreter/`, no `~/.local/share/open-interpreter/`, no session logs outside the venv. Open Interpreter v0.4.3 stores NO state outside the virtualenv in the default configuration. This is a major difference from Claude Code (308 persistent files in `~/.claude/`) — Open Interpreter has an **ephemeral session model**. |
| Short-window file write bursts aligned with command execution | **Observed** | `phase3-agentic/workspace-files.txt` | `app.py` (221 bytes) and `test_app.py` (719 bytes after fix) created at 15:10 within seconds. `.pytest_cache/` and `__pycache__/` created at 15:10–15:11. Tight temporal clustering confirms burst-write pattern from shell command execution. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| No config/state directory created outside venv | `phase4-teardown/oi-config-final.txt` | Unlike Claude Code (`~/.claude/`) and Ollama (`~/.ollama/`), Open Interpreter creates zero persistent state directories. All session data is ephemeral. This means file-based post-hoc detection is limited to finding the venv itself or workspace artifacts. |
| Venv contains the entire detection footprint | `phase1-install/venv-disk-usage.txt` | 590 MB venv at `~/oi-lab-venv/`. Deleting the venv eliminates nearly all forensic evidence. The only surviving artifacts are workspace files created during execution and pip cache. |
| Jupyter kernel infrastructure | `phase1-install/pip-venv-packages.txt` | Dependencies include `ipykernel`, `jupyter-client`, `jupyter-core`, `pyzmq` — Open Interpreter runs code through a Jupyter kernel. This is detectable via the `ipykernel_launcher` process and ZMQ socket activity. |
| Massive dependency tree as detection surface | `phase1-install/pip-install-output.txt` | 135+ packages including distinctive combinations: `litellm` (multi-provider LLM router), `anthropic` + `openai` + `google-generativeai` (multi-provider SDK), `selenium` + `webdriver-manager` (browser automation), `tiktoken` (tokenization). This dependency fingerprint is highly distinctive. |

**Layer signal strength: 0.65** (Venv package is a strong artifact when found, but zero persistent state outside the venv limits post-hoc detection. File writes during execution are confirmed but task-dependent.)

### Network Layer

| IOC (Playbook Section 4.7) | Status | Evidence | Notes |
|---|---|---|---|
| Model-provider API calls with burst timing matching action loops | **Observed differently** | `phase3-agentic/connections-stream.txt`, `phase2-launch/model-backend.txt` | Connected to `localhost:11434` (Ollama) rather than cloud API. Each code generation step triggered an LLM call to the local endpoint. In a cloud-API scenario (OpenAI/Anthropic), the traffic would be short-lived HTTPS to `api.openai.com` or `api.anthropic.com` — same challenge as Claude Code for polling-based capture. The Ollama fallback actually produced a stronger network signal (persistent localhost connection). |
| Outbound requests triggered as part of command workflows | **Observed** | `phase3-agentic/agentic-session-output.txt` | `pip install flask pytest` triggered outbound connections to PyPI (`files.pythonhosted.org`). This is a network signal *from within the agentic session* — the tool's command execution caused secondary network activity. Network monitoring would see: (1) LLM API calls, (2) PyPI package downloads — distinguishable by destination but temporally correlated. |

**Layer signal strength: 0.55** (Network target varies by model provider configuration — not a fixed indicator like Claude Code's `api.anthropic.com`. With local Ollama, localhost traffic is easily captured. Cloud API traffic would face the same polling capture challenges as Claude Code. Secondary network activity from command execution is a useful corroborative signal.)

### Identity / Access Layer

| IOC (Playbook Section 4.7) | Status | Evidence | Notes |
|---|---|---|---|
| Endpoint user identity mapped to interpreter runtime session | **Observed** | `phase2-launch/privilege-context.txt`, `phase3-agentic/python-process-stream.txt` | Process runs as user `echance` (uid=503). Process ownership clearly attributable via `ps` and `lsof`. No dedicated service user — runs under the invoking user's identity. |
| Credential/token exposure in runtime environment | **Observed (structurally)** | `baseline/api-key-check.txt`, `phase2-launch/credential-exposure-check.txt` | `OPENAI_API_KEY` was present in the environment (though quota was exhausted). The API key was accessible to the interpreter process via environment variables. No credential exposure was detected in `ps` process arguments. **Key finding:** credentials are passed via env vars, not stored in config files — they are accessible to the process but not persisted to disk by Open Interpreter. This differs from Claude Code (which stores OAuth creds in `~/.claude/backups/`). |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| No persistent credential store | `phase4-teardown/oi-config-final.txt` | Open Interpreter stores no credentials on disk. API keys come from environment variables or CLI arguments. This means identity attribution depends on correlating the runtime environment with the user session — no post-hoc credential artifacts to find. |
| Model provider determines identity depth | `phase2-launch/model-backend.txt` | With Ollama (local): zero identity beyond OS user. With OpenAI: OPENAI_API_KEY ties to an OpenAI account. With Anthropic: ANTHROPIC_API_KEY. Identity strength is entirely dependent on the configured model backend. |

**Layer signal strength: 0.55** (OS user identity confirmed. Credential presence in env vars is structural but not persisted. No account profile, no OAuth, no org context. Identity depth depends on model provider configuration.)

### Behavior Layer

| IOC (Playbook Section 4.7) | Status | Evidence | Notes |
|---|---|---|---|
| Plan→execute→revise loops with command bursts | **Observed** | `phase3-agentic/agentic-session-output.txt` | The LLM-driven session generated code, then OI's code execution engine ran it via shell. The plan→execute pattern was visible in the session output: LLM generates JSON tool call → OI executes code → output captured → next step. With the 1B local model, the planning quality was poor, but the *mechanism* was clearly observed. |
| Repeated shell/file operations with low inter-command delay | **Observed** | `phase3-agentic/workspace-files.txt`, `phase3-agentic/agentic-session-output.txt` | Five consecutive code execution operations completed in ~30 seconds: file creation (app.py), file creation (test_app.py), pip install, pytest run, Python code execution. Low inter-command delay confirmed — the tool chains operations rapidly without human review. |
| Package install + execution chain in same loop (risk marker) | **Observed** | `phase3-agentic/agentic-session-output.txt` | `pip install flask pytest` followed immediately by `pytest test_app.py -v` within the same OI session. This is the risk marker IOC — the tool installed packages AND executed code that depended on them in a single autonomous loop. In a governed environment, this would be a high-risk signal. |
| Credential-store touches / broad file fan-out in restricted paths (risk marker) | **Not observed** | `phase3-agentic/privilege-escalation-check.txt` | The scoped task did not trigger credential-store access or restricted-path writes. This IOC is task-dependent — a broader task (e.g., "configure my SSH keys" or "update system settings") would trigger it. |

**Layer signal strength: 0.85** (Three of four behavioral IOCs confirmed. The command-chain pattern — the primary risk signal for Open Interpreter — was clearly observed. Package-install-then-execute is the strongest behavioral differentiator.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.70               0.210
File / Artifact      0.20      0.65               0.130
Network              0.15      0.55               0.083
Identity / Access    0.15      0.55               0.083
Behavior             0.20      0.85               0.170
                                          ──────────────
base_score                                         0.675
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (chain observed via IPyKernel)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard venv install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[△] Non-default artifact paths:                  −0.10  → PARTIAL: −0.05
    (Venv location is user-chosen, not a well-known path like ~/.claude/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct to Ollama/PyPI)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Python PID to network not continuously attributed; polling gaps)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[△] Weak/missing identity correlation:           −0.10  → PARTIAL: −0.05
    (OS user identified, but no account/org context; credential env-only)
                                                 ──────
penalties                                         0.15
```

### Final Score

```
final_confidence = 0.675 - 0.15 = 0.525

Classification: Medium (0.45 ≤ 0.525 < 0.75)
```

### Score Assessment

The Medium classification feels **appropriate** for Open Interpreter with polling-based instrumentation. The score is notably lower than Claude Code (0.71) despite both being Class C tools, for three structural reasons:

1. **Process layer is weaker:** Generic `python3` process name vs Claude Code's distinctive `claude` binary. Requires module-path inspection rather than simple binary name matching.
2. **File layer is much weaker:** Zero persistent state directories vs Claude Code's 308-file `~/.claude/`. Detection depends on finding the venv, which can be located anywhere.
3. **Behavioral layer is the strongest signal** — this is inverted from Claude Code where File was strongest. For Open Interpreter, the command-chain execution pattern is the primary detection anchor.

**Projected score with EDR-grade telemetry:** ~0.68 (still Medium). Even with continuous process-to-network correlation, the identity and file layers remain structurally weaker than Claude Code. EDR would improve process detection (module-path matching) but the ephemeral artifact problem persists.

**Key insight:** Open Interpreter is **harder to detect and attribute** than Claude Code despite being the same risk class (C). The Python/venv architecture, generic process name, and ephemeral session model all reduce detection confidence. This has implications for Class C weight profiles — they may need to be tool-specific, not class-generic.

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | Medium (0.525) |
| Tool Class | C (Autonomous Executor — auto_run active) |
| Asset Sensitivity | Tier 0 (home directory, non-sensitive test project) |
| Action Risk | R2 (scoped writes in non-protected path) + R3 (shell execution + package install) |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Rule 2: Medium confidence + Tier 0/1 + R2 → **Warn**
- Rule 3: Medium confidence + R3 (shell execution + package install in same loop) → **Approval Required**

**Decision: Warn with step-up to Approval Required** for the shell execution + package install chain.

This matches Claude Code's policy decision (LAB-RUN-001), confirming that Class C tools in agentic mode consistently trigger the R3 escalation path.

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-006
Date:                2026-03-02
Tool:                Open Interpreter v0.4.3 (open-interpreter pip package)
Scenario ID:         OI-POS-01 (Standard venv install + agentic command execution)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive
Model Backend:       Ollama local (llama3.2:1b) — fallback from OpenAI quota

Signal Observations:
  Process:           OBSERVED — python3 process with interpreter module. Parent chain:
                     zsh → python3 → ipykernel → bash → pip/pytest. Process name is
                     generic 'python3', not 'interpreter' — weaker than Claude Code.
                     Evidence: phase1-install/binary-metadata.txt,
                     phase3-agentic/python-process-stream.txt
  File/Artifact:     OBSERVED — interpreter package in venv/site-packages (590 MB).
                     ZERO persistent state outside venv. No ~/.config/open-interpreter/.
                     Workspace files created during execution. Ephemeral session model.
                     Evidence: phase1-install/interpreter-package-contents.txt,
                     phase4-teardown/oi-config-final.txt
  Network:           OBSERVED — localhost:11434 (Ollama) for LLM calls. PyPI downloads
                     from command execution. Cloud API target varies by provider config.
                     Evidence: phase3-agentic/connections-stream.txt
  Identity:          PARTIALLY OBSERVED — OS user echance (uid=503). API key in env vars
                     (not persisted). No account profiles, no OAuth, no org context.
                     Identity depth depends on model provider.
                     Evidence: phase2-launch/privilege-context.txt,
                     baseline/api-key-check.txt
  Behavior:          OBSERVED — command-chain execution (create → install → test) in
                     rapid sequence with auto_run=True. Package install + execution
                     chain (risk marker) confirmed. Plan→execute loop observed.
                     Evidence: phase3-agentic/agentic-session-output.txt,
                     phase3-agentic/workspace-files.txt

Confidence Result:   0.525 (Medium) — five-layer model
                     Projected with EDR: ~0.68 (Medium)
Policy Decision:     Warn / Approval Required (Rules 2+3, Section 6.3)
Evidence Links:      78 files across 5 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Generic python process name reduces detection specificity;
                     zero persistent state limits post-hoc forensics;
                     venv location is arbitrary (no well-known path);
                     auto_run flag eliminates all safety confirmation;
                     model provider configuration changes network target
```

---

## 5. Class C Cross-Comparison: Open Interpreter vs Claude Code

| Dimension | Claude Code (LAB-RUN-001) | Open Interpreter (LAB-RUN-006) | Significance |
|---|---|---|---|
| **Final score** | 0.71 (Medium) | 0.525 (Medium) | −0.185 gap — OI is materially harder to detect |
| **Strongest layer** | File (0.95) | Behavior (0.85) | Inverted anchors — Claude Code is file-rich; OI is behaviorally distinctive |
| **Weakest layer** | Network (0.30) | Identity/Network (0.55/0.55) | Claude Code's weakness is instrumental; OI's is architectural |
| **Process name** | `claude` (distinctive) | `python3` (generic) | OI requires deeper inspection (module paths, venv context) |
| **Persistent state** | 308 files in `~/.claude/` | Zero outside venv | Claude Code leaves a large forensic footprint; OI is ephemeral |
| **Identity anchor** | OAuth profile in JSON | API key in env var (if set) | Claude Code has rich, stored identity; OI has transient, env-only |
| **Code execution model** | Direct subprocess (claude → sh) | Jupyter kernel (python → ipykernel → sh) | OI adds an indirection layer that complicates lineage |
| **Permission model** | Interactive confirmation | `auto_run=True` bypasses all | OI's safety boundary is weaker by design |
| **Install mechanism** | npm global (well-known path) | pip in arbitrary venv | OI's install location is user-chosen, not predictable |
| **Persistence posture** | Zero active persistence | Zero active persistence | Both are on-demand CLI tools with no daemons |

**Key finding:** Class C confidence profiles are NOT generalizable across tools. Claude Code and Open Interpreter have the same risk class but very different detection profiles. Weight calibration must be tool-specific within Class C.

---

## 6. Proposed Layer Weight Calibration for Open Interpreter (Class C)

Based on empirical observations, the default five-layer weights should be adjusted for Open Interpreter:

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Generic `python3` name reduces process-layer value. Module-path matching required. |
| File | 0.20 | 0.15 | Ephemeral session model — zero state outside venv. Venv location is arbitrary. |
| Network | 0.15 | 0.15 | No change — provider-dependent target, same polling challenges as Claude Code. |
| Identity | 0.15 | 0.10 | Env-var credentials only, no persistent identity store. Weaker than Claude Code's OAuth. |
| Behavior | 0.20 | 0.35 | **Dominant signal.** Command-chain pattern is the primary detection anchor. Package-install-then-execute is highly distinctive. |

**Recalculated score with proposed weights:**

```
Layer                Weight    Signal Strength    Weighted
Process              0.25      0.70               0.175
File                 0.15      0.65               0.098
Network              0.15      0.55               0.083
Identity             0.10      0.55               0.055
Behavior             0.35      0.85               0.298
                                          ──────────────
base_score                                         0.708
penalties                                          0.15
final_confidence                                   0.558

Classification: Medium (0.45 ≤ 0.558 < 0.75)
```

Still Medium, but the score distribution better reflects the actual signal profile. Behavior dominates — this is the correct characterization for a tool whose primary risk is autonomous command execution.

---

## 7. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **Process name is generic `python3`, not `interpreter`.** The entrypoint at `~/oi-lab-venv/bin/interpreter` is a Python console_script — when running, it appears as `python3` in `ps`. Detection rules matching binary names (like `node.*claude` for Claude Code) will not work. Must match Python processes with `interpreter` module paths in arguments. | Section 4.7 Process IOC | Clarify: "Process appears as `python3` in process listings, NOT as `interpreter`. Detection requires matching Python interpreter processes with `open-interpreter` or `interpreter.terminal_interface` in module paths or command arguments." |
| 2 | **Open Interpreter uses Jupyter/IPyKernel for code execution.** Code is executed through a Jupyter kernel subprocess, adding an indirection layer. Process chain is: python3 (interpreter) → python3 (ipykernel_launcher) → bash → commands. This complicates parent-child lineage detection. | Section 4.7 Process IOC | Add IOC: "Jupyter/IPyKernel subprocess (`ipykernel_launcher`) as child of interpreter process. Presence of IPyKernel alongside `open-interpreter` in the same venv is a corroborative signal." |
| 3 | **Zero persistent state outside the virtualenv.** No `~/.config/open-interpreter/`, no `~/.local/share/open-interpreter/`, no session logs. All state is ephemeral. This makes post-hoc detection dependent on finding the venv or workspace artifacts. | Section 4.7 File IOC | Update: "Session history/transcript artifacts" should note: "v0.4.3 stores NO persistent state outside the virtualenv. Post-hoc detection requires venv discovery or workspace artifact analysis. Contrast with Claude Code (308 persistent files)." |
| 4 | **Venv install location is arbitrary and unpredictable.** Unlike `~/.claude/` (fixed path) or `/opt/homebrew/bin/ollama` (well-known), a venv can be created anywhere. This makes artifact-sweep detection harder — must scan for `interpreter` package in any Python site-packages. | Section 4.7 File IOC | Add note: "Virtualenv location is user-chosen. Detection cannot rely on a fixed path. Artifact sweeps must search for `interpreter` package across all Python environments (system, user, venv, conda)." |
| 5 | **Dependency fingerprint is highly distinctive.** 135+ packages including unique combination: `litellm` + `anthropic` + `openai` + `google-generativeai` + `selenium` + `tiktoken` + `ipykernel`. This package combination is unlikely to appear in non-AI-tool contexts. | Section 4.7 File IOC (new) | Add IOC: "Distinctive dependency fingerprint in pip package list: `litellm` + multi-provider SDKs (anthropic, openai, google-generativeai) + `selenium` + `tiktoken`. Confidence Weight: Medium." |
| 6 | **`auto_run=True` eliminates all safety confirmations.** With this flag (or `-y` CLI), Open Interpreter executes ALL generated code without any human approval. This is the highest-risk configuration and is trivially enabled. Claude Code always prompts for shell execution approval. | Section 4.7 Behavior IOC, Section 7 | Add risk note: "`auto_run=True` / `-y` flag disables all execution confirmation. Detection of this flag in process arguments or configuration is itself a high-risk signal. Consider adding as a risk marker IOC." |
| 7 | **Model provider is configurable — network target is not fixed.** Open Interpreter can contact OpenAI, Anthropic, Google, local Ollama, or any LiteLLM-compatible endpoint. Network detection cannot rely on a fixed destination domain. Config analysis or traffic pattern matching is required. | Section 4.7 Network IOC | Update: "Model-provider API calls" should note: "Provider target varies by configuration. May connect to api.openai.com, api.anthropic.com, localhost:11434, or custom endpoints. Network IOC must match on traffic pattern (burst timing, request shape) rather than fixed destination." |
| 8 | **Behavioral layer is the primary detection anchor for Open Interpreter, not File.** Unlike Claude Code (File=0.95 strongest) or Ollama (Process/File=0.90 strongest), Open Interpreter's strongest signal is the command-chain execution pattern. Weight profiles must be tool-specific within Class C. | Section 12 (Methodology), Appendix B | Add lesson: "Class C confidence profiles are not generalizable. Claude Code is file-anchored; Open Interpreter is behavior-anchored. Per-tool weight calibration within the same class is empirically justified." |
| 9 | **OpenAI quota exhaustion was recoverable via Ollama fallback.** The lab demonstrated the multi-provider architecture — when OpenAI failed, Ollama provided local inference. This confirms the network-target variability risk and shows the tool can silently switch providers. | Section 4.7 Network IOC | Add note: "Open Interpreter can transparently switch model providers. Network monitoring for a single API endpoint is insufficient. The tool may fail over from cloud to local (or vice versa) without user-visible changes." |
| 10 | **Credential exposure via environment variables is structural but not persisted.** The `OPENAI_API_KEY` was accessible to the interpreter process but never written to disk. This is a different risk profile from Claude Code (which stores OAuth creds in `~/.claude/backups/`): higher runtime risk (env var visible to all child processes), lower forensic risk (nothing persists). | Section 4.7 Identity IOC | Clarify credential exposure risk: "API keys passed via env vars are accessible to ALL child processes spawned by OI (including shell commands). Runtime credential exposure is broader than Claude Code's OAuth model. However, no credentials persist to disk — forensic credential recovery is not possible." |

---

## 8. Summary

Open Interpreter v0.4.3 is **detectable but harder to attribute** than Claude Code despite sharing the same Class C risk classification. The tool has a fundamentally different detection profile: weak on process naming and file persistence, strong on behavioral command-chain patterns.

**Key detection anchors (in priority order):**

1. Command-chain execution pattern: python → ipykernel → bash → pip/pytest (Behavior — highest confidence)
2. `open-interpreter` package in Python site-packages with distinctive dependency fingerprint (File — requires venv discovery)
3. `auto_run=True` / `-y` flag enabling unconfirmed execution (Behavior — risk marker)
4. Package-install-then-execute within a single session (Behavior — risk marker)
5. Model provider API traffic with LLM burst timing (Network — provider-dependent)

**Key governance challenges (in priority order):**

1. **Ephemeral session model** — zero persistent state outside the venv means limited post-hoc forensics
2. **Generic process name** — `python3` does not reveal tool identity without deeper inspection
3. **Arbitrary venv location** — no well-known path for artifact sweeps
4. **Configurable model provider** — network target is not fixed
5. **`auto_run` flag** — trivially removes all safety confirmations

**Playbook validation status:** 10 of 14 IOCs from Section 4.7 confirmed or partially confirmed. 4 IOCs not observed (1 task-dependent, 3 architecturally different from predicted). 10 new findings to feed back into the playbook. Proposed Open Interpreter-specific weight calibration with Behavior dominating at 0.35.

**Class C generalizability verdict:** Class C weight profiles are NOT generalizable. Open Interpreter and Claude Code have the same risk class but need different detection strategies and weight calibrations. The playbook should maintain tool-specific profiles within Class C.
