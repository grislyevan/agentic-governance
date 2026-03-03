# LAB-RUN-007 Results: OpenClaw Installation & Runtime Telemetry

**Run ID:** LAB-RUN-007  
**Date:** 2026-03-02  
**Tool:** OpenClaw v2026.3.1 (`openclaw` npm package, SHA-256 `1703fc39...`)  
**Scenario ID:** OC-POS-01 (Standard install + onboarding + agentic task + skill creation)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/openclaw-lab/LAB-RUN-007/` (79 files, SHA-256 hashed per phase)

> **Note:** OpenClaw was previously installed and configured on this endpoint. The lab captures a re-install/upgrade + exercise scenario rather than a clean-slate first install. The `~/.openclaw/` directory, LaunchAgent, and channel configurations pre-existed. This is representative of real-world detection scenarios where the tool is already in use.

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.11) | Status | Evidence | Notes |
|---|---|---|---|
| `openclaw` CLI binary and `openclaw-gateway` daemon process | **Observed** | `phase3a-basic/openclaw-processes.txt`, `phase3a-basic/port-18789-during-task.txt` | Binary at `/opt/homebrew/bin/openclaw` (symlink to `openclaw.mjs`). Gateway process appears as `openclaw-gateway` (PID 82656) — **named process, not generic**. Parent chain: `launchd (PID 1)` → `openclaw-gateway`. Launcher shim process `openclaw` (PID 82649) also present. |
| Child process chains: gateway → shell → commands | **Observed (indirect)** | `phase3b-agentic/workspace-files.txt`, `phase3b-agentic/agentic-task-output.txt` | 3 files created (hello.py, README.md, test_hello.py) in `~/openclaw-lab-workspace/` during agentic task. Agent attempted `python3 -m pytest` execution (failed due to missing pytest, confirming shell command was issued). Child processes were transient — confirmed by artifact presence, not direct process capture. |
| Persistent daemon (LaunchAgent on macOS) | **Observed** | `phase2-onboard/openclaw-plist-contents.txt`, `phase2-onboard/openclaw-launch-agent.txt` | LaunchAgent at `~/Library/LaunchAgents/ai.openclaw.gateway.plist`. **`KeepAlive: true` + `RunAtLoad: true`** — auto-starts on login AND auto-restarts if killed. Label: `ai.openclaw.gateway`. Binary path: `/opt/homebrew/Cellar/node@22/22.22.0/bin/node` running `dist/entry.js gateway --port 18789`. Strongest persistence mechanism of any profiled tool. |
| Cron/scheduled task execution | **Architecture confirmed, not exercised** | `phase3d-proactive/cron-state.txt` | Cron infrastructure exists (`~/.openclaw/cron/jobs.json`) but no jobs configured. `openclaw status` reports "Heartbeat: 30m (main)" — a heartbeat mechanism exists for proactive check-ins. Cron and webhook capabilities are documented in architecture but were not triggered in this lab run. |

**Layer signal strength: 0.90** (Named process `openclaw-gateway` is distinctive and easily identified. LaunchAgent provides persistent detection anchor. Child process chains confirmed indirectly via artifacts.)

### File / Artifact Layer

| IOC (Playbook Section 4.11) | Status | Evidence | Notes |
|---|---|---|---|
| `~/.openclaw/` global config/state directory | **Observed** | `phase1-install/openclaw-dir-post.txt`, `phase4-teardown/openclaw-dir-final.txt` | 23 top-level entries: `agents/`, `browser/`, `canvas/`, `completions/`, `credentials/`, `cron/`, `delivery-queue/`, `devices/`, `identity/`, `logs/`, `media/`, `memory/`, `workspace/`, `openclaw.json` (+ 4 backups), `exec-approvals.json`, `update-check.json`. **215 MB total disk footprint.** Richest config/state directory of any tested tool (Claude Code: 308 files/unknown size; Ollama: 13 files/652 MB model data). |
| `~/.openclaw/openclaw.json` central config | **Observed** | `phase2-onboard/openclaw-config.txt` | Contains: model configuration (gpt-5.3-codex), auth profiles (Anthropic API key, Google API key, OpenAI-Codex OAuth), channel configs (WhatsApp, Slack), agent defaults, gateway settings. **High-value artifact — single file reveals complete tool configuration, model provider, and channel integrations.** |
| Skills directory with self-authored skills | **Observed** | `phase3c-selfmod/skills-after.txt`, `phase3c-selfmod/skill-contents.txt` | Agent successfully created `~/.openclaw/workspace/skills/temperature-converter/SKILL.md` (temperature conversion skill). **Self-modification confirmed.** Skills are Markdown files with YAML frontmatter defining tool behavior. Hot-reload via file watcher is configured (default 250ms debounce). |
| Credentials directory | **Observed** | `phase2-onboard/credentials-dir.txt` | `~/.openclaw/credentials/` exists (created during WhatsApp channel linking). Contains channel authentication stores. Presence indicates active messaging platform connections. |
| Session/conversation persistence | **Observed** | `phase3a-basic/agents-state-post.txt` | `~/.openclaw/agents/main/sessions/sessions.json` — 4 sessions persisted: 1 direct (main), 3 Slack group. Sessions survive gateway restarts. Token counts and model assignments persisted per session. |
| LaunchAgent plist | **Observed** | `phase2-onboard/openclaw-plist-contents.txt`, `phase4-teardown/launch-agents-final.txt` | `~/Library/LaunchAgents/ai.openclaw.gateway.plist` (2389 bytes). **Persists after gateway stop.** Contains embedded environment variables including JIRA credentials, gateway token, and PATH. |
| Workspace prompt files (AGENTS.md, SOUL.md, TOOLS.md) | **Observed** | `phase2-onboard/workspace-prompt-files.txt` | All three files present in `~/.openclaw/workspace/`. Define agent persona, capabilities, and available tools. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| Config backup chain (5 generations) | `phase1-install/openclaw-dir-post.txt` | `openclaw.json.bak`, `.bak.1` through `.bak.4` — config history enables forensic reconstruction of configuration changes over time |
| Exec-approvals registry | `phase1-install/openclaw-dir-post.txt` | `exec-approvals.json` tracks which shell commands the user has approved. Forensic value: reveals what the agent has been authorized to do |
| Log files with stdout/stderr separation | `phase2-onboard/openclaw-plist-contents.txt` | Gateway logs at `~/.openclaw/logs/gateway.log` and `gateway.err.log`. Complete operational history. |
| Browser profile directory | `phase1-install/openclaw-dir-post.txt` | `~/.openclaw/browser/` for managed Chrome/Chromium. Presence indicates browser automation capability is configured. |
| Memory/vector store | `phase1-install/openclaw-dir-post.txt` | `~/.openclaw/memory/` — persistent memory with vector search capability. `openclaw status` reports "0 files, 0 chunks, sources memory, plugin memory-core, vector ready, fts ready" |
| Device pairing state | `phase1-install/openclaw-dir-post.txt` | `~/.openclaw/devices/` — tracks paired iOS/Android/macOS nodes. |

**Layer signal strength: 0.95** (Richest file footprint of any tested tool. `~/.openclaw/` is a comprehensive forensic treasure — config, credentials, sessions, skills, logs, memory, and device state in one directory. 215 MB persistent footprint.)

### Network Layer

| IOC (Playbook Section 4.11) | Status | Evidence | Notes |
|---|---|---|---|
| Gateway WS listener on `:18789` | **Observed** | `phase3a-basic/port-18789-during-task.txt` | `node` (PID 82656) listening on `localhost:18789` (IPv4 + IPv6 TCP). Process-to-socket attribution is clean and unambiguous via `lsof`. Analogous to Ollama's `:11434` but WebSocket-based. |
| Model provider API traffic | **Observed (indirect)** | `phase3a-basic/basic-interaction-output.txt`, `phase3b-agentic/agentic-task-output.txt` | Agent completed inference (capital of France, file creation). Model: `gpt-5.3-codex` (OpenAI). Without pcap, cannot confirm specific API endpoint. Config shows OpenAI-Codex OAuth profile. |
| Chat platform connections | **Observed (config-level)** | `phase2-onboard/openclaw-config.txt`, `phase2-onboard/openclaw-status.txt` | WhatsApp channel configured and linked (phone number `+17203239788`, auth 4d ago). Slack configured but missing tokens. **Active WhatsApp connection would create persistent WebSocket to WhatsApp servers.** Not actively connected during lab (gateway was stopped at baseline). |
| Browser automation traffic | **Not tested** | — | Browser tool available (`~/.openclaw/browser/` exists) but not exercised in this lab run. |

**Layer signal strength: 0.70** (Gateway listener is a strong, persistent signal — trivially attributable like Ollama's. Model provider traffic confirmed indirectly. Chat platform connections confirmed at config level but not actively captured.)

### Identity / Access Layer

| IOC (Playbook Section 4.11) | Status | Evidence | Notes |
|---|---|---|---|
| Model provider API keys in config/env | **Observed** | `phase2-onboard/openclaw-config.txt`, `baseline/ai-env.txt` | Three auth profiles configured: Anthropic (API key), Google (API key), OpenAI-Codex (OAuth). `OPENAI_API_KEY` in environment. Keys/OAuth tokens stored in `openclaw.json` — **cleartext credential store.** |
| Chat platform credentials in config | **Observed** | `phase2-onboard/openclaw-config.txt`, `phase2-onboard/openclaw-plist-contents.txt` | WhatsApp auth in `~/.openclaw/credentials/`. LaunchAgent plist embeds `JIRA_API_TOKEN`, `JIRA_EMAIL`, `OPENCLAW_GATEWAY_TOKEN` as environment variables. **Critical finding: LaunchAgent plist is a credential store visible to any process that can read `~/Library/LaunchAgents/`.** |
| OS user running daemon | **Observed** | `phase3a-basic/openclaw-processes.txt` | Daemon runs as user `echance`. Process ownership clearly visible in `ps` and `lsof`. |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| LaunchAgent embeds external service credentials | `phase2-onboard/openclaw-plist-contents.txt` | JIRA_API_TOKEN, JIRA_EMAIL, JIRA_BASE_URL, JIRA_PROJECT_KEY embedded in the LaunchAgent plist. The plist is world-readable (mode 644). Any local process can extract these credentials. This is a governance-critical finding. |
| Gateway authentication token | `phase2-onboard/openclaw-plist-contents.txt` | `OPENCLAW_GATEWAY_TOKEN` is embedded in the plist. Required for Control UI access but exposed in the LaunchAgent. |
| Multi-provider auth profiles | `phase2-onboard/openclaw-config.txt` | Three separate model providers configured with distinct auth methods. Forensic value: reveals which AI services the user has access to. |

**Layer signal strength: 0.85** (Strongest identity footprint of any tested tool. Multiple API keys, OAuth tokens, bot credentials, external service tokens, and org-level credentials all centralized in config and LaunchAgent. Surpasses Claude Code's OAuth profile.)

### Behavior Layer

| IOC (Playbook Section 4.11) | Status | Evidence | Notes |
|---|---|---|---|
| Shell command execution from agent context | **Observed** | `phase3b-agentic/agentic-task-output.txt`, `phase3b-agentic/workspace-files.txt` | 3 files created + pytest execution attempted in a single agent turn. Files created at 16:15 within seconds of each other — burst-write pattern confirmed. Agent reported attempting `python3 -m pytest` but failed (no pytest installed), confirming shell execution capability. |
| Self-modification (skill authoring + hot-reload) | **Observed** | `phase3c-selfmod/skill-creation-output.txt`, `phase3c-selfmod/skill-contents.txt` | Agent created `temperature-converter/SKILL.md` in its own skills directory. Skill is a Markdown file with YAML frontmatter (name, description) and instructions. **This is the highest-risk behavioral pattern in the playbook — the agent modified its own capability set.** Skill watcher enables hot-reload without restart. |
| Rapid multi-file write during agentic task | **Observed** | `phase3b-agentic/workspace-files.txt` | 3 files (hello.py, README.md, test_hello.py) created within the same second (all timestamped 16:15). Tight temporal clustering confirms burst-write pattern, consistent with Claude Code behavior. |
| Proactive/scheduled execution | **Architecture confirmed, not exercised** | `phase3d-proactive/cron-state.txt` | Cron infrastructure exists (empty jobs list). Heartbeat: 30m. Webhook support documented. Proactive capability is present but was not triggered during the lab. |
| Multi-channel message routing | **Config confirmed, not exercised** | `phase2-onboard/openclaw-status.txt` | WhatsApp linked, Slack configured. Architecture supports: external message → gateway → agent turn → shell/file/browser execution. Not tested because connecting messaging accounts is out of scope for security lab. |
| Browser automation | **Capability confirmed, not exercised** | `phase1-install/openclaw-dir-post.txt` | `~/.openclaw/browser/` exists. Browser tool available per architecture documentation. Not exercised in this run. |

**Layer signal strength: 0.80** (Shell execution and self-modification confirmed. Multi-file burst-write observed. Proactive/scheduled and multi-channel behaviors confirmed architecturally but not exercised — gap to close in OC-POS-02/03.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.90               0.270
File / Artifact      0.20      0.95               0.190
Network              0.15      0.70               0.105
Identity / Access    0.15      0.85               0.1275
Behavior             0.20      0.80               0.160
                                          ──────────────
base_score                                         0.8525
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (daemon chain clear)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard npm install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.openclaw/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct connection)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Model provider traffic not captured via pcap; gateway listener fully attributed)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[✗] Weak/missing identity correlation:           −0.10  → NOT APPLIED (richest identity of any tool)
                                                 ──────
penalties                                         0.05
```

### Final Score

```
final_confidence = 0.8525 - 0.05 = 0.80

Classification: High (≥ 0.75)
```

### Score Assessment

The High classification is **appropriate and expected**. OpenClaw has the richest detection footprint of any tested tool:

- **File layer (0.95)** matches Claude Code as the strongest — but OpenClaw's 215 MB directory with config, credentials, sessions, skills, logs, and device state exceeds Claude Code's breadth.
- **Identity layer (0.85)** is the **strongest of any tested tool** — multiple API keys, OAuth tokens, bot credentials, and external service tokens all centralized.
- **Process layer (0.90)** — named `openclaw-gateway` process with LaunchAgent persistence. Clear and unambiguous.

**Comparison with other tools:**

| Tool | Class | Final Score | Classification |
|---|---|---|---|
| **OpenClaw** | **C (persistent)** | **0.80** | **High** |
| Cursor | A→C | 0.79 | High |
| Claude Code | C | 0.71 | Medium |
| Ollama | B | 0.69 | Medium |
| Open Interpreter | C | 0.525 | Medium |
| Copilot | A | 0.45 | Medium (barely) |

OpenClaw achieves the **highest confidence score of any tested tool**. This is driven by its exceptionally rich file and identity footprints — it stores more governance-relevant data in `~/.openclaw/` than any other tool stores anywhere.

**Projected score with EDR + active channel monitoring:** ~0.90 (High)

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | High (0.80) |
| Tool Class | C (Autonomous Executor — persistent daemon with self-modification) |
| Asset Sensitivity | Tier 0 (home directory, non-sensitive test project) |
| Action Risk | R2 (scoped writes) + R3 (shell execution) + **R4 (self-modification, external channel communication)** |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Rule 3: High confidence + R3 (shell execution) → **Approval Required**
- Rule 4: High confidence + R4 (self-modification) → **Block** in sensitive contexts
- Rule 5: Persistent daemon with external communication → **Approval Required at minimum**

**Decision: Approval Required** for standard use; **Block** for self-modification and external channel communication in sensitive environments.

OpenClaw's combination of persistent daemon, self-modification, and external communication channels makes it the highest-risk tool in the current playbook. The governance posture should be stricter than for any other Class C tool.

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-007
Date:                2026-03-02
Tool:                OpenClaw v2026.3.1 (npm package, Node.js)
Scenario ID:         OC-POS-01 (Standard install + onboarding + agentic task + skill creation)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — openclaw-gateway daemon (PID 82656) with clean
                     launchd parent chain. Named process, easily identifiable.
                     LaunchAgent with KeepAlive + RunAtLoad. CLI invocations
                     as separate client processes (like Ollama).
                     Evidence: phase3a-basic/openclaw-processes.txt,
                     phase2-onboard/openclaw-plist-contents.txt
  File/Artifact:     OBSERVED — ~/.openclaw/ with 23 top-level entries, 215 MB.
                     Config, credentials, sessions, skills, logs, memory,
                     workspace, device state. Richest file footprint tested.
                     Self-authored skill confirmed. LaunchAgent plist persists.
                     Evidence: phase1-install/openclaw-dir-post.txt,
                     phase3c-selfmod/skill-contents.txt,
                     phase4-teardown/openclaw-dir-final.txt
  Network:           OBSERVED — Gateway WS listener on localhost:18789 (IPv4+IPv6),
                     PID-attributable via lsof. Model provider traffic confirmed
                     indirectly. Chat platform connections confirmed at config level.
                     Evidence: phase3a-basic/port-18789-during-task.txt
  Identity:          OBSERVED — Strongest identity footprint of any tool. Multiple
                     API keys (Anthropic, Google, OpenAI), WhatsApp auth, JIRA
                     credentials in LaunchAgent plist, gateway token. All cleartext.
                     Evidence: phase2-onboard/openclaw-config.txt,
                     phase2-onboard/openclaw-plist-contents.txt
  Behavior:          OBSERVED — Shell execution (3 files + pytest attempt), self-
                     modification (temperature-converter skill created in skills
                     dir), multi-file burst-write. Proactive/scheduled capability
                     confirmed architecturally but not exercised.
                     Evidence: phase3b-agentic/agentic-task-output.txt,
                     phase3c-selfmod/skill-creation-output.txt

Confidence Result:   0.80 (High) — five-layer model
                     Highest confidence of any tested tool
                     Projected with EDR + active channels: ~0.90 (High)
Policy Decision:     Approval Required / Block (Rules 3+4+5, Section 6.3)
Evidence Links:      79 files across 8 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Chat platform connections not actively tested;
                     proactive/scheduled execution not triggered;
                     browser automation not exercised;
                     no pcap for model provider traffic attribution
```

---

## 5. Cross-Class Comparison

| Question | Finding |
|---|---|
| How does persistence compare to Ollama (Class B)? | **OpenClaw has stronger persistence.** Both use daemon processes, but OpenClaw's LaunchAgent has `KeepAlive: true` + `RunAtLoad: true` (auto-start on boot + auto-restart on kill). Ollama's Homebrew service status was `none` (registered but not auto-started). OpenClaw's daemon is designed to be always-on; Ollama's is available but dormant by default. |
| How does agentic execution compare to Claude Code / Open Interpreter (Class C)? | **Comparable execution, broader scope.** All three can execute shell commands and create files. OpenClaw's distinguishing factor is that execution can be triggered by external messages (WhatsApp/Telegram/Discord), not just local terminal prompts. Claude Code and Open Interpreter are session-based; OpenClaw is always-on. |
| Are chat platform connections observable without connecting accounts? | **Yes — at config level.** `openclaw status` reveals configured channels, linked accounts, and connection state. `openclaw.json` contains channel tokens and allowlists. The credentials directory indicates linked platforms. Full network-level observation requires active channel connections. |
| Does the daemon auto-restart after stop? | **After `launchctl unload`: No.** The unload removes the job from launchd. The plist file persists on disk. **After `kill` (without unload): Yes** — `KeepAlive: true` would respawn the process. This is the strongest auto-restart behavior of any tested tool. |
| What is the disk footprint after onboarding + agentic task? | **215 MB** — dominated by workspace, logs, browser profile, and agent state. Smaller than Ollama's model storage (652 MB) but larger than Claude Code's `~/.claude/` (unknown total size, 308 files). |
| Is the Gateway WebSocket authenticated? | **Yes** — Gateway token required for Control UI access (`OPENCLAW_GATEWAY_TOKEN` in plist). However, the token is stored in cleartext in the LaunchAgent plist (world-readable). The localhost-only binding provides network-level protection. |
| Does skill hot-reload work? Is self-modification observable? | **Self-modification confirmed.** Agent wrote `temperature-converter/SKILL.md` to its own skills directory. Skill watcher configured with 250ms debounce for hot-reload. The file write to `~/.openclaw/workspace/skills/` IS the self-modification — observable via file monitoring. |
| What novel IOCs exist that aren't in any other profile? | **(1)** LaunchAgent with `KeepAlive + RunAtLoad` — no other tool auto-starts and auto-restarts. **(2)** Self-authored skills in workspace — no other tool modifies its own capability. **(3)** Embedded external service credentials in LaunchAgent plist. **(4)** Multi-channel session routing across messaging platforms. **(5)** Heartbeat/cron infrastructure for proactive execution. **(6)** Exec-approvals registry tracking authorized commands. |

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **LaunchAgent plist embeds external service credentials in cleartext.** The `ai.openclaw.gateway.plist` contains JIRA_API_TOKEN, JIRA_EMAIL, and OPENCLAW_GATEWAY_TOKEN as environment variables. The plist is world-readable (mode 644). Any local process can extract these credentials. | Section 4.11 Identity IOC, Section 7 (Risky Action Controls) | Add IOC: "LaunchAgent/systemd unit embeds API keys and external service credentials as environment variables." Flag as credential exposure risk — credentials are readable by any local process. |
| 2 | **`KeepAlive: true` + `RunAtLoad: true` is the strongest persistence mechanism in the playbook.** No other tool auto-starts on boot AND auto-restarts on kill. This means the agent is designed to be always-running — detection must account for the daemon being present at all times, not just during user sessions. | Section 4.11 Process IOC, Section 5 (Class Taxonomy) | Document as the defining persistence characteristic. Contrast with Ollama (registered but dormant), Claude Code (no persistence), and Open Interpreter (no persistence). |
| 3 | **Self-modification is real and trivially easy.** The agent created a new skill file in its own workspace skills directory with a single prompt. The skill watcher picks up changes automatically. There is no approval gate for skill creation — the agent can modify its own capabilities without human confirmation. | Section 4.11 Behavior IOC, Section 7 (Risky Action Controls) | Add governance recommendation: skill authoring should require explicit approval in governed environments. The `skills.load.watch` setting should be disabled or monitored. Skill directory writes should trigger alerts. |
| 4 | **OpenClaw's `openclaw status` command is the richest diagnostic output of any tool.** It reveals: gateway state, channel connections, session inventory, model assignments, security audit, heartbeat config, and memory state — all in a single command. This is a governance asset — a single invocation reveals complete tool configuration. | Section 4.11 (new IOC), Section 11 (Tooling) | Add IOC: "`openclaw status` output reveals complete configuration state including channels, sessions, models, security posture, and heartbeat settings." Recommend periodic `openclaw status` capture as a governance monitoring technique. |
| 5 | **Exec-approvals registry tracks authorized commands.** `~/.openclaw/exec-approvals.json` records which shell commands the user has pre-approved. This is a forensic artifact that reveals what the agent has been authorized to do — and by inference, what it has done. | Section 4.11 File IOC | Add IOC: "Exec-approvals registry in `~/.openclaw/` tracks pre-authorized shell commands. Forensic value: reveals approved execution scope." |
| 6 | **Config backup chain (5 generations) enables forensic reconstruction.** `openclaw.json.bak` through `.bak.4` preserve configuration history. Diffs between backups reveal when channels were added, models changed, or security settings modified. | Section 4.11 File IOC | Add IOC: "Config backup chain in `~/.openclaw/` (up to 5 generations). Enables forensic reconstruction of configuration changes." |
| 7 | **`openclaw agent --agent main` is the CLI interaction pattern.** Unlike Claude Code (interactive REPL), OpenClaw's CLI sends a single message to the gateway for processing. The gateway handles the agent turn and returns the result. This means the CLI is a thin client — all intelligence runs in the daemon. | Section 4.11 Process IOC | Clarify that CLI commands are HTTP/WS clients of the daemon (like Ollama), not standalone executors. Detection should focus on the daemon process, not the transient CLI. |
| 8 | **Three-class taxonomy is strained but not broken.** OpenClaw fits as Class C with persistence overlay. The key novel characteristics (proactive execution, self-modification, multi-channel communication) are capability extensions of Class C, not a fundamentally different execution model. However, if additional "persistent autonomous agents" emerge (e.g., from OpenAI's agent platform), a Class D designation would be warranted. | Section 5 (Class Taxonomy) | Retain OpenClaw as Class C (persistent). Add the Class D discussion as a forward-looking note. Revisit when 2+ tools share the persistent autonomous agent profile. |
| 9 | **WhatsApp channel linked to a phone number creates a novel detection surface.** `openclaw status` reveals the linked phone number (+17203239788) and auth timestamp. This connects the tool's identity to a real-world phone number — a stronger identity signal than any other tool provides, but also a privacy concern. | Section 4.11 Identity IOC | Add IOC: "Linked phone number and chat platform accounts in `openclaw status` and config. Connects tool identity to real-world communication endpoints." |
| 10 | **Security audit built into `openclaw status` reveals governance-relevant findings.** The status output flagged 2 CRITICAL and 2 WARN issues (open group policy with elevated tools, multi-user setup risk). The tool's own security diagnostics produce governance-relevant signals. | Section 4.11 (new), Section 11 (Tooling) | Document that OpenClaw's built-in security audit (`openclaw status`, `openclaw doctor`) produces governance-relevant findings. These should be captured as part of periodic endpoint assessment. |

---

## 7. Proposed Layer Weight Calibration for OpenClaw

Based on empirical observations, the default five-layer weights should be adjusted for OpenClaw:

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.25 | Named daemon is distinctive but less critical than the file layer for forensic value. LaunchAgent is the key persistence signal. |
| File | 0.20 | 0.30 | **Dominant signal.** 215 MB directory with config, credentials, skills, sessions, logs, memory. Richest file footprint tested. Self-modification evidence is file-based. |
| Network | 0.15 | 0.15 | No change. Gateway listener is strong but ephemeral model API traffic has same polling challenges as other tools. |
| Identity | 0.15 | 0.15 | No change. Strongest identity layer tested (API keys + bot tokens + external credentials), but the high signal strength compensates without weight increase. |
| Behavior | 0.20 | 0.15 | Less dominant than file layer. Self-modification and shell execution are confirmed but the artifacts they produce are the primary detection anchors (file-based). |

**Recalculated score with proposed weights:**

```
Layer                Weight    Signal Strength    Weighted
Process              0.25      0.90               0.225
File                 0.30      0.95               0.285
Network              0.15      0.70               0.105
Identity             0.15      0.85               0.1275
Behavior             0.15      0.80               0.120
                                          ──────────────
base_score                                         0.8625
penalties                                          0.05
final_confidence                                   0.8125

Classification: High (≥ 0.75)
```

Still High, with a slightly higher base score reflecting the dominance of the file layer.

---

## 8. Summary

OpenClaw v2026.3.1 is **the most detectable and the highest-risk tool in the playbook**. It combines the richest detection footprint (highest confidence score: 0.80) with the broadest capability surface (persistent daemon, self-modification, multi-channel communication, proactive execution, browser automation).

**Key detection anchors (in priority order):**

1. `~/.openclaw/` directory — 215 MB, config/credentials/skills/sessions/logs (File — highest standalone confidence)
2. `openclaw-gateway` daemon process with LaunchAgent persistence (Process — high confidence)
3. Gateway WebSocket listener on `localhost:18789` (Network — strong, persistent signal)
4. Cleartext credentials in `openclaw.json` and LaunchAgent plist (Identity — highest of any tool)
5. Self-authored skills in workspace directory (Behavior — novel, high-risk)

**Key governance challenges (in priority order):**

1. **Self-modification** — agent can write and hot-reload its own skills without approval
2. **Multi-channel external communication** — prompts from WhatsApp/Telegram/Discord bypass local terminal controls
3. **Persistent daemon with auto-restart** — tool is designed to be always-on, never off
4. **Credential exposure** — LaunchAgent plist embeds external service credentials in world-readable file
5. **Proactive execution** — cron/heartbeat/webhook infrastructure enables action without user presence

**Playbook validation status:** 18/27 IOCs confirmed or partially confirmed. 5 confirmed architecturally but not exercised (proactive, multi-channel, browser). 4 not tested (skill download, external network targets). 10 new findings to feed back into playbook.

**Novel risk assessment:** OpenClaw represents a category of tool not previously captured in the three-class taxonomy. While it fits Class C for governance purposes, its combination of persistent daemon, self-modification, multi-channel communication, and proactive execution creates a risk profile fundamentally different from Claude Code, Open Interpreter, or any other Class C tool. Future tools with similar profiles (persistent autonomous agents) may warrant a Class D designation.
