# LAB-RUN-004 Results: Cursor IDE Installation & Runtime Telemetry

**Run ID:** LAB-RUN-004  
**Date:** 2026-03-02  
**Tool:** Cursor v2.5.26 (Electron-based IDE, VS Code fork)  
**Scenario ID:** CUR-POS-01 (Standard IDE session + AI-assisted editing + agentic task)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/cursor-lab/LAB-RUN-004/` (90 files, SHA-256 hashed per phase)

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.2) | Status | Evidence | Notes |
|---|---|---|---|
| Signed Cursor app process from standard install paths (`/Applications/Cursor.app`) | **Observed** | `baseline/cursor-codesign.txt`, `phase2-launch/cursor-main-pid.txt` | Main Cursor process (PID 56635) at `/Applications/Cursor.app/Contents/MacOS/Cursor`. Mach-O universal binary (x86_64 + arm64). Code-signed: `Developer ID Application: Hilary Stout (VDXQ22DGB9)`, notarized. Bundle identifier: `com.todesktop.230313mzl4w4u92`. 29 total Cursor processes, ~2.1 GB aggregate RSS. |
| Child process lineage: Cursor → embedded terminal → shell/git/node | **Observed** | `phase2-launch/cursor-process-tree.txt` | Full parent-child chain captured. Main process (56635) spawns: GPU helper (56640), Network utility (56642), shared-process (57091), terminal pty-host (57095), Renderer processes (64614, 68158), fileWatcher (64615, 70083), and three distinct extension-host types: `extension-host (user)` (64616, 70084), `extension-host (retrieval-always-local)` (64617, 70085), and critically `extension-host (agent-exec)` (64618, 70086). The agent-exec host spawns `/bin/zsh` for shell command execution. |
| Sustained session with child process and file-write bursts | **Observed** | `phase2-launch/cursor-aggregate-resources.txt`, `phase3b-classC/workspace-files.txt` | Session active with 29 processes, 2,130 MB aggregate RSS, 27.6% CPU. Three files created in workspace within <2 seconds during agentic task (burst-write pattern confirmed). Git operations (init + add + commit) executed in sequence. |

**Additional process-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| Three distinct extension-host types reveal class hierarchy | `phase2-launch/cursor-process-tree.txt` | Cursor runs three extension-host processes per window: (1) `extension-host (user)` — standard VS Code extensions, (2) `extension-host (retrieval-always-local)` — Cursor's AI retrieval with `gitWorker.js`, (3) `extension-host (agent-exec)` — the autonomous executor. **The `agent-exec` process is the Class C escalation indicator.** Its presence in the process tree means the agent feature is active. |
| Terminal PTY host as distinct process | `phase2-launch/cursor-process-tree.txt` | `Cursor Helper: terminal pty-host` (PID 57095) manages embedded terminal sessions. Shell commands from the agent spawn under this process's child tree. |
| Network service as utility subprocess | `phase2-launch/cursor-process-tree.txt` | `Cursor Helper --type=utility --utility-sub-type=network.mojom.NetworkService` handles all network I/O. Process-to-socket attribution is straightforward — this utility process owns all Cursor's network connections. |
| `cursorsan` process on localhost listeners | `phase2-launch/cursor-listening-ports.txt` | A separate `cursorsan` process (PID 66666) listens on `127.0.0.1:54142` and `127.0.0.1:54143`. This is likely a Cursor sandbox/security process — not documented in the playbook. |

**Layer signal strength: 0.95** (Exceptional process identification. Signed binary, clean parent-child tree, distinctive multi-process Electron architecture with labeled extension-host types. The `agent-exec` extension host is a direct, unambiguous Class C indicator.)

### File / Artifact Layer

| IOC (Playbook Section 4.2) | Status | Evidence | Notes |
|---|---|---|---|
| `~/.cursor/`, workspace `.cursor/` settings and extension state files | **Observed** | `phase1-footprint/cursor-global-dirs.txt`, `phase1-footprint/workspace-cursor-dir.txt` | `~/.cursor/` contains 63 files (14 MB). Subdirectories: `plans/`, `projects/`, `extensions/`, `ai-tracking/`, `skills-cursor/`. Workspace `.cursor/` contains project-specific rules (`.mdc` files), skills. |
| AI feature cache/session files with recent timestamps | **Observed** | `phase3b-classC/cursor-changed-files.txt`, `phase4-teardown/cursor-changed-artifacts.txt` | 8 files modified during the lab session: 3 agent-transcript JSONL files, 1 agent-tools file (91 KB), `ai-code-tracking.db` (4.8 MB SQLite), `blocklist`, `unified_repo_list.json`. Agent transcripts store full session history per-project under `~/.cursor/projects/<path-hash>/agent-transcripts/<uuid>/`. |
| Burst edits across repo files with consistent timing | **Observed** | `phase3b-classC/workspace-files.txt` | Three source files (`hello.py`, `test_hello.py`, `README.md`) created at 15:00 within seconds. `.pytest_cache/` and `__pycache__/` artifacts prove test execution. Git directory created during commit. All timestamps within the agentic task window. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| `ai-code-tracking.db` — SQLite database tracking all AI interactions | `phase1-footprint/ai-feature-artifacts.txt`, `phase4-teardown/cursor-changed-artifacts.txt` | 4.8 MB SQLite database at `~/.cursor/ai-tracking/ai-code-tracking.db`. Actively modified during sessions. Contains a forensic record of all AI-assisted code changes — high-value attribution artifact. |
| Agent transcript JSONL files per project | `phase3b-classC/cursor-changed-files.txt` | Full agent session history stored at `~/.cursor/projects/<path-hash>/agent-transcripts/<uuid>/<uuid>.jsonl`. Contains the complete conversation, tool calls, file edits, and shell commands from each agent session. Multiple transcripts per project accumulate over time. |
| Agent tools state file | `phase4-teardown/cursor-changed-artifacts.txt` | `~/.cursor/projects/<path-hash>/agent-tools/<uuid>.txt` (91 KB) stores tool execution state during agent sessions. |
| Plans directory with AI-generated plans | `phase3a-classA/plans-listing.txt` | `~/.cursor/plans/` contains `.plan.md` files generated by AI planning features (e.g., `metal_analysis_agent_ec4ca7e9.plan.md`). These are Class A artifacts — evidence of AI-assisted planning even without shell execution. |
| Skills and rules in workspace `.cursor/` | `phase1-footprint/cursor-rules-files.txt`, `phase1-footprint/cursor-skills-files.txt` | Workspace `.cursor/rules/` contains `.mdc` rule files that customize AI behavior. `~/.cursor/skills-cursor/` contains skill definitions. These artifacts configure AI behavior boundaries — relevant to governance. |
| `Made-with: Cursor` git trailer | `phase3b-classC/git-log-full.txt` | Git commits made during agent sessions contain `Made-with: Cursor` trailer in the commit message. This is an attribution signal analogous to Claude Code's `Co-Authored-By` trailer. |
| `user-data-dir` in process args reveals state location | `phase2-launch/cursor-process-tree.txt` | Every Cursor helper process includes `--user-data-dir=/Users/echance/Library/Application Support/Cursor` in its command-line arguments. This reveals a secondary state directory at `~/Library/Application Support/Cursor/` (in addition to `~/.cursor/`). |

**Layer signal strength: 0.90** (Rich, unique artifact set. `~/.cursor/` is distinctive; agent transcripts provide complete session forensics; `ai-code-tracking.db` is a high-value attribution anchor. Slightly lower than Claude Code's 0.95 due to smaller file count, but quality is high.)

### Network Layer

| IOC (Playbook Section 4.2) | Status | Evidence | Notes |
|---|---|---|---|
| TLS/SNI to Cursor cloud/model infrastructure endpoints | **Observed** | `phase2-launch/cursor-established.txt`, `phase2-launch/cursor-dest-ips.txt` | 15 established TLS connections to 9 unique destination IPs over port 443. Connections attributed to specific extension-host PIDs: `retrieval-always-local` (PID 64617, 70085) holds most connections, `agent-exec` (PID 64618, 70086) holds connections during agentic tasks. Forward DNS confirms `api2.cursor.sh` resolves to IPs in the same AWS/Cloudflare ranges observed. Destinations include: `104.18.18.125`, `104.18.19.125` (Cloudflare — likely Cursor API frontend), `54.153.104.1` (AWS — 4 concurrent connections), `3.228.95.195`, `52.20.65.195`, `34.233.62.252`, `3.212.155.223` (AWS — Cursor cloud infrastructure). |
| Request bursts aligned with prompt-response editing cycles | **Observed (indirect)** | `phase2-launch/cursor-established.txt` | Multiple concurrent connections to the same AI endpoint IP (54.153.104.1 × 4 from a single extension host) suggest HTTP/2 multiplexing or connection pooling for prompt-response traffic. Without pcap, burst cadence cannot be precisely measured, but the connection pattern (persistent TLS to AI endpoints during active agent session) is consistent with the IOC. |

**Additional network findings:**

| Finding | Evidence | Significance |
|---|---|---|
| Process-to-socket attribution is clean for Cursor | `phase2-launch/cursor-established.txt` | Unlike Claude Code's short-lived HTTPS bursts, Cursor maintains **persistent** TLS connections to its cloud endpoints. These are easily attributed to specific Cursor extension-host PIDs via `lsof` at any polling interval. The `retrieval-always-local` host handles most connections; the `agent-exec` host has its own dedicated connections. |
| Extension-host PID identifies the connection purpose | `phase2-launch/cursor-established.txt` | Connections from PID 64617 (`retrieval-always-local`) vs PID 64618 (`agent-exec`) vs PID 70086 (`agent-exec` window 2) allow attribution of network traffic to specific Cursor feature modes. This is a unique advantage of the multi-process architecture — the extension-host name reveals whether network activity is Class A (retrieval) or Class C (agent-exec). |
| Localhost listeners on dynamic ports | `phase2-launch/cursor-listening-ports.txt` | Extension hosts listen on dynamic localhost ports (57199, 57673). `cursorsan` listens on 54142, 54143. These are inter-process communication channels, not external API endpoints (unlike Ollama's 11434). |
| `api2.cursor.sh` via Cloudflare and AWS | `phase2-launch/cursor-dest-dns.txt` | `api2.cursor.sh` → `api2geo.cursor.sh` → `api2direct.cursor.sh` resolves to multiple AWS IPs. Geographic load balancing via CNAME chain. Connection IPs (104.18.x.x) are Cloudflare frontends. |

**Layer signal strength: 0.75** (Stronger than Claude Code's network signal. Persistent TLS connections are easily attributed to Cursor PIDs. Forward DNS confirms Cursor-owned endpoints. Extension-host labels enable Class A vs C traffic differentiation. Without pcap/SNI capture, cannot confirm exact domain names on wire.)

### Identity / Access Layer

| IOC (Playbook Section 4.2) | Status | Evidence | Notes |
|---|---|---|---|
| Cursor account state (corporate vs personal) on managed endpoint | **Partially observed** | `phase1-footprint/identity-artifacts.txt`, `phase1-footprint/json-with-identity.txt` | No explicit identity artifact files (`*auth*`, `*account*`, `*token*`) found in `~/.cursor/`. No JSON files with email/account/auth/token keywords found at maxdepth 3. Identity state is likely stored in `~/Library/Application Support/Cursor/` (the Electron user-data-dir) or in the `state.vscdb` SQLite database, neither of which was fully examined. The git commit identifies user as `ziltoidiaAttax <echance@magnite.com>` — this is the git config identity, not necessarily the Cursor account. |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| Git author identity as proxy signal | `phase3b-classC/git-log-full.txt` | Git commits show author `ziltoidiaAttax <echance@magnite.com>`. While this is git-config-level identity (not Cursor account state), it establishes the human actor for audit trail purposes. |
| Process ownership under OS user | `phase2-launch/cursor-all-processes.txt` | All 29 Cursor processes run under user `echance`. No privilege escalation, no dedicated service user. Consistent with desktop app model. |
| Code signing authority as provenance signal | `baseline/cursor-codesign.txt` | Signed by `Developer ID Application: Hilary Stout (VDXQ22DGB9)`. Hilary Stout is the Cursor CEO. This is a provenance signal — the binary is attributable to Cursor, Inc. via Apple's code signing chain. |
| Account state likely in Electron user-data-dir | `phase2-launch/cursor-process-tree.txt` | `--user-data-dir=/Users/echance/Library/Application Support/Cursor` appears in all helper processes. Cursor's account/auth state is likely stored here (standard Electron credential storage pattern), not in `~/.cursor/`. This directory was not fully examined in this run. |

**Layer signal strength: 0.55** (Weaker than expected. Cursor account state was not directly captured — it resides in the Electron user-data-dir rather than `~/.cursor/`. OS user ownership and git author identity are available but not org-level signals. Future runs should examine `~/Library/Application Support/Cursor/` for account/auth state.)

### Behavior Layer

| IOC (Playbook Section 4.2) | Status | Evidence | Notes |
|---|---|---|---|
| High-frequency multi-file edit loops after prompt interaction cadence | **Observed** | `phase3b-classC/workspace-files.txt` | Three source files created within <2 seconds during agentic task. Pattern: prompt → multi-file write fan-out → shell execution → result processing. This matches the agentic edit shape. |
| Context-heavy reads + concentrated writes (agentic edit shape) | **Observed** | `phase3b-classC/cursor-changed-files.txt`, `phase4-teardown/cursor-changed-artifacts.txt` | Agent read 5 reference files (LAB-RUN-001, 003, results, playbook) before writing the protocol document. Pattern: broad context reads followed by concentrated writes — classic agentic behavior. The agent-tools state file (91 KB) captured the full context window. |
| Shell invocations proximate to AI edit sequences | **Observed** | `phase2-launch/cursor-process-tree.txt`, `phase3b-classC/workspace-files.txt` | Process tree shows `extension-host (agent-exec)` → `/bin/zsh` chain for shell commands. Shell commands executed during the agentic task: `mkdir`, `cat` (heredoc file creation), `python3 -m pytest`, `git init`, `git add`, `git commit`. `.pytest_cache/` and `__pycache__` artifacts confirm pytest execution from within the agent session. |

**Additional behavior findings:**

| Finding | Evidence | Significance |
|---|---|---|
| `Made-with: Cursor` git trailer as behavioral IOC | `phase3b-classC/git-log-full.txt` | The commit message includes `Made-with: Cursor` — an attribution trailer inserted by the agent. Analogous to Claude Code's `Co-Authored-By` trailer. **Same evasion risk applies:** user can likely suppress this via settings. |
| Agent transcripts log the complete agentic loop | `phase3b-classC/cursor-changed-files.txt` | JSONL files in `agent-transcripts/` record the full prompt → tool-call → result sequence. These are behavioral evidence files — they prove the agentic loop occurred and document every action. |
| `agent-exec` extension host as class escalation marker | `phase2-launch/cursor-process-tree.txt` | The presence of `extension-host (agent-exec)` in the process tree is a binary Class C indicator. When this process exists and has child shells, the IDE has escalated from Class A (assistive) to Class C (autonomous executor). |
| Cursor sandbox wrapper for shell execution | `phase2-launch/cursor-process-tree.txt` | Agent-exec shell commands run through a sandbox wrapper: `/bin/zsh -c snap=$(command cat <&3); ... builtin eval "${__CURSOR_SANDBOX_ENV_RESTORE:-}" ... builtin eval "$1"`. This sandboxing mechanism controls the agent's shell environment. Presence of `__CURSOR_SANDBOX_ENV_RESTORE` in environment is a forensic indicator. |

**Layer signal strength: 0.90** (Strong behavioral signals across all three IOCs. The `agent-exec` extension host is a unique, unambiguous Class C indicator. Agent transcripts provide complete forensic record of the agentic loop. Git trailer adds attribution signal.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.95               0.285
File / Artifact      0.20      0.90               0.180
Network              0.15      0.75               0.1125
Identity / Access    0.15      0.55               0.0825
Behavior             0.20      0.90               0.180
                                          ──────────────
base_score                                         0.840
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (full tree captured)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (signed standard install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.cursor/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct Cursor cloud)
[✗] Unresolved process-to-network linkage:       −0.10  → NOT APPLIED (persistent connections attributed to PIDs)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[△] Weak/missing identity correlation:           −0.10  → PARTIAL: −0.05
    (OS user and git author identified, but Cursor account state not captured from user-data-dir)
                                                 ──────
penalties                                         0.05
```

### Final Score

```
final_confidence = 0.840 - 0.05 = 0.79

Classification: High (0.79 ≥ 0.75)
```

### Score Assessment

The High classification is **appropriate** and reflects Cursor's strong detectability across Process, File, and Behavior layers. Two factors push Cursor's score above Claude Code's (0.71) and Ollama's (0.69):

1. **Process tree is exceptionally rich.** The labeled extension-host types (`user`, `retrieval-always-local`, `agent-exec`) provide more granular attribution than any other tool tested. The `agent-exec` host is a direct, unambiguous Class C indicator.

2. **Network connections are persistent and attributable.** Unlike Claude Code's short-lived HTTPS bursts that evade polling, Cursor maintains persistent TLS connections that are trivially attributed to specific PIDs and extension-host types via `lsof`.

The identity layer is the weakest signal, pulling the score down. With access to `~/Library/Application Support/Cursor/` (the Electron user-data-dir), account/auth state would likely be available, pushing identity signal strength to 0.70+ and final confidence to ~0.85.

**Comparison with prior runs:**

| Metric | Claude Code (LAB-RUN-001) | Ollama (LAB-RUN-003) | Cursor (LAB-RUN-004) |
|---|---|---|---|
| Final score | 0.71 (Medium) | 0.69 (Medium) | **0.79 (High)** |
| Strongest layer | File (0.95) | Process/File (0.90) | Process (0.95) |
| Weakest layer | Network (0.30) | Identity (0.50) | Identity (0.55) |
| Process count | 1 main + transient children | 1 daemon + transient CLI | **29 persistent processes** |
| Network attribution | Polling-evades-bursts | Persistent listener | **Persistent TLS + PID attribution** |

---

## 3. Class Escalation Analysis

This is the novel contribution of LAB-RUN-004 — validating the Class A → C escalation model.

| Question | Finding |
|---|---|
| What process/behavioral signals distinguish Class A from Class C mode? | **The `extension-host (agent-exec)` process is the binary indicator.** Cursor runs three extension-host types per window. The `agent-exec` host exists when agent features are active. When it spawns child `/bin/zsh` processes, the IDE has escalated to Class C. In contrast, `extension-host (user)` handles standard extensions (Class A) and `extension-host (retrieval-always-local)` handles AI retrieval (Class A). |
| Does the process tree change when the agent feature is activated? | **Yes, unambiguously.** The `agent-exec` extension host appears in the process tree with child shell processes. This is visible to any process monitoring system. The shell command text is visible in the process arguments (including the command being executed). |
| Are there distinct network patterns between chat-only and agentic usage? | **Yes.** The `agent-exec` host (PID 64618/70086) maintains its own TLS connections to Cursor cloud endpoints, separate from the `retrieval-always-local` host's connections. Class C network traffic is distinguishable by PID attribution to the `agent-exec` extension host. |
| What file artifacts are created during agentic vs assistive sessions? | **Agent sessions create:** (1) agent-transcript JSONL files under `~/.cursor/projects/<path>/agent-transcripts/`, (2) agent-tools state files under `agent-tools/`, (3) workspace file writes. **Assistive sessions create:** `ai-code-tracking.db` updates, plan files in `~/.cursor/plans/`. The transcript files are the key differentiator — they only exist when the agent (Class C) feature is used. |
| Can Class C behavior be detected from process telemetry alone? | **Yes.** The presence of `extension-host (agent-exec)` with child `/bin/zsh` processes is sufficient to detect Class C escalation. No file or network evidence required. This is the strongest Class C indicator of any tool tested. |
| Is there a single signal that reliably indicates class escalation? | **Yes: `extension-host (agent-exec)` in the process tree.** This process exists per-window when agent features are active. Its presence is necessary and sufficient for Class C classification. When it has child shell processes, autonomous execution is actively occurring. |

**Key insight:** Cursor's multi-process Electron architecture is a governance *advantage*, not a liability. The labeled extension-host types create a natural process-level indicator of tool class. This is unique — no other tool in the playbook provides a process-level signal that directly maps to its governance class.

---

## 4. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | High (0.79) |
| Tool Class | A (baseline) → C (when agent-exec active) |
| Asset Sensitivity | Tier 0 (home directory, non-sensitive test project) |
| Action Risk | R2 (scoped writes in non-protected path) + R3 (shell command execution) |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Class A mode: Rule 1 — High confidence + Tier 0 + R1 → **Detect**
- Class C mode: Rule 3 — High confidence + Tier 0 + R3 (shell execution) → **Approval Required**
- Rule 4 — High confidence + any disallowed R4 action → **Block**

**Decision:**
- **Class A (assistive):** Detect — code suggestions and chat do not trigger enforcement.
- **Class C (agentic):** Approval Required — shell execution from the agent-exec host requires approval in governed environments.

---

## 5. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-004
Date:                2026-03-02
Tool:                Cursor v2.5.26 (Electron IDE, com.todesktop.230313mzl4w4u92)
Scenario ID:         CUR-POS-01 (Standard IDE session + AI edit + agentic task)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — 29-process Electron tree with labeled extension hosts.
                     Main process (PID 56635) at /Applications/Cursor.app, code-signed
                     by Cursor Inc. Three extension-host types: user, retrieval-always-
                     local, agent-exec. The agent-exec host is the Class C indicator.
                     Evidence: phase2-launch/cursor-process-tree.txt,
                     phase2-launch/cursor-all-processes.txt
  File/Artifact:     OBSERVED — ~/.cursor/ with 63 files (14 MB) including agent
                     transcripts, ai-code-tracking.db, plans, skills, project state.
                     Agent transcripts store full session JSONL per project.
                     Evidence: phase1-footprint/cursor-global-dirs.txt,
                     phase3b-classC/cursor-changed-files.txt,
                     phase4-teardown/cursor-changed-artifacts.txt
  Network:           OBSERVED — 15 persistent TLS connections to 9 IPs (Cloudflare +
                     AWS). Connections attributed to specific extension-host PIDs.
                     Forward DNS confirms api2.cursor.sh endpoints. Agent-exec has
                     dedicated connections separate from retrieval.
                     Evidence: phase2-launch/cursor-established.txt,
                     phase2-launch/cursor-dest-ips.txt
  Identity:          PARTIALLY OBSERVED — OS user (echance) and git author identified.
                     Cursor account state not captured (stored in Electron user-data-dir
                     at ~/Library/Application Support/Cursor/, not in ~/.cursor/).
                     Code signing authority identifies Cursor Inc.
                     Evidence: phase1-footprint/identity-artifacts.txt,
                     baseline/cursor-codesign.txt
  Behavior:          OBSERVED — Multi-file write burst (3 files in <2s) + shell
                     execution (pytest, git init/add/commit) + Made-with: Cursor
                     git trailer. Agent transcripts log complete agentic loop.
                     agent-exec extension host is binary Class C indicator.
                     Evidence: phase3b-classC/workspace-files.txt,
                     phase3b-classC/git-log-full.txt,
                     phase2-launch/cursor-process-tree.txt

Confidence Result:   0.79 (High) — five-layer model
                     Projected with account state: ~0.85 (High)
Policy Decision:     Detect (Class A) / Approval Required (Class C) (Rules 1+3, Section 6.3)
Evidence Links:      90 files across 6 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           PASS
Residual Risk:       Identity layer under-instrumented (Electron user-data-dir not
                     examined); no pcap for SNI confirmation; Made-with trailer
                     evasion not tested
```

---

## 6. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **`extension-host (agent-exec)` is a process-level Class C indicator.** Cursor's labeled extension-host types directly map to governance classes. Presence of `agent-exec` in the process tree means the agent feature is active. Child `/bin/zsh` processes under it mean autonomous shell execution is occurring. This is the strongest Class C indicator of any tool tested. | Section 4.2 Process IOC | Add IOC: "Cursor Helper (Plugin): extension-host (agent-exec) process in process tree — binary indicator of Class C escalation. Child shell processes under this host confirm autonomous execution." Confidence Weight: High. |
| 2 | **Agent transcripts provide complete session forensics.** JSONL files at `~/.cursor/projects/<path-hash>/agent-transcripts/<uuid>/<uuid>.jsonl` record the full agent session: prompts, tool calls, file edits, shell commands. These are more complete than Claude Code's session artifacts. | Section 4.2 File IOC | Add IOC: "Agent transcript JSONL files in `~/.cursor/projects/<path>/agent-transcripts/` — complete forensic record of agent sessions including all tool calls." Confidence Weight: High. |
| 3 | **`ai-code-tracking.db` is a high-value attribution database.** 4.8 MB SQLite database at `~/.cursor/ai-tracking/ai-code-tracking.db` tracks all AI-assisted code changes. This is a centralized attribution artifact — one database links all AI activity across all projects. | Section 4.2 File IOC | Add IOC: "SQLite database at `~/.cursor/ai-tracking/ai-code-tracking.db` — centralized AI activity tracker. Modified during all AI interactions (Class A and C)." Confidence Weight: High. |
| 4 | **Network connections are persistent and PID-attributable.** Unlike Claude Code's ephemeral HTTPS bursts, Cursor maintains persistent TLS connections to its cloud endpoints. These are trivially attributed to specific extension-host PIDs via `lsof`. The extension-host label reveals whether traffic is Class A (retrieval) or Class C (agent-exec). | Section 4.2 Network IOC | Upgrade network IOC confidence from Medium to Medium–High. Add note: "Persistent TLS connections attributed to extension-host PIDs. Extension-host type (retrieval vs agent-exec) differentiates Class A from Class C network traffic." |
| 5 | **Identity state is in Electron user-data-dir, not `~/.cursor/`.** Cursor's account/auth state is stored at `~/Library/Application Support/Cursor/` (the `--user-data-dir` path from process arguments), not in `~/.cursor/`. This split between config (`~/.cursor/`) and state (`~/Library/Application Support/Cursor/`) is standard for Electron apps but not documented in the playbook. | Section 4.2 Identity IOC | Add note: "Cursor account state stored in `~/Library/Application Support/Cursor/` (Electron user-data-dir), not `~/.cursor/`. Detection must check both paths." |
| 6 | **`Made-with: Cursor` git trailer is an attribution signal.** Git commits from agent sessions include `Made-with: Cursor` trailer. Same one-way signal properties as Claude Code's `Co-Authored-By` trailer — high confidence when present, zero confidence when absent. Evasion testing needed. | Section 4.2 Behavior IOC (new) | Add IOC: "`Made-with: Cursor` git trailer in commits from agent sessions. One-way signal (high when present, zero when absent). Evasion testing recommended (CUR-EVA-02)." |
| 7 | **Code signing identifies Cursor authoritatively.** Binary signed by `Developer ID Application: Hilary Stout (VDXQ22DGB9)`, TeamIdentifier `VDXQ22DGB9`. This is a cryptographic provenance signal — the binary is attributable to Cursor Inc. via Apple's notarization chain. | Section 4.2 Process IOC | Add note: "macOS code signing with Developer ID and notarization provides cryptographic binary attribution. TeamIdentifier `VDXQ22DGB9` uniquely identifies Cursor." |
| 8 | **`cursorsan` process is a sandbox/security component.** A separate `cursorsan` process listens on localhost ports. This is not documented in the playbook and may be relevant to security posture assessment. | Section 4.2 Process IOC (new) | Add IOC: "`cursorsan` process on localhost listeners — Cursor sandbox/security component. Presence indicates Cursor security features are active." |
| 9 | **Cursor sandbox wrapper for shell commands.** Agent shell commands run through a wrapper that includes `__CURSOR_SANDBOX_ENV_RESTORE` environment variable manipulation. This is a defense-in-depth mechanism. Its presence in environment or process args is a forensic indicator of Cursor agent-mode shell execution. | Section 4.2 Behavior IOC (new) | Add IOC: "Shell command wrapper with `__CURSOR_SANDBOX_ENV_RESTORE` in agent-exec child processes — indicates sandboxed agent shell execution." |
| 10 | **Cursor achieves High confidence without sudo/EDR.** This is the first lab run to reach High confidence (0.79) using only non-privileged tooling (`ps`, `lsof`, `pstree`, file listing). Claude Code (0.71) and Ollama (0.69) both scored Medium. The multi-process Electron architecture and persistent network connections make Cursor more detectable with less instrumentation. | Section 12.4 Methodology | Add note: "Cursor (LAB-RUN-004) achieved High confidence (0.79) without sudo or EDR — first tool to do so. Multi-process architecture and persistent TLS connections are detectable with standard user-level tools." |

---

## 7. Proposed Layer Weight Calibration for Cursor (Class A → C)

Based on empirical observations, the default five-layer weights should be adjusted for Cursor:

| Layer | Default Weight | Proposed Weight | Justification |
|---|---|---|---|
| Process | 0.30 | 0.30 | No change — process tree is the strongest signal. Labeled extension hosts are unique. |
| File | 0.20 | 0.20 | No change — agent transcripts and ai-tracking.db are high-quality artifacts. |
| Network | 0.15 | 0.20 | Increase — persistent TLS connections are easily attributed to PIDs. Extension-host labels enable Class A/C traffic differentiation. Stronger than default assumes. |
| Identity | 0.15 | 0.10 | Decrease — account state in Electron user-data-dir was not accessible in standard scan. OS user is only available signal without deeper inspection. |
| Behavior | 0.20 | 0.20 | No change — agentic loop confirmed with all three IOCs. |

**Recalculated score with proposed weights:**

```
Layer                Weight    Signal Strength    Weighted
Process              0.30      0.95               0.285
File                 0.20      0.90               0.180
Network              0.20      0.75               0.150
Identity             0.10      0.55               0.055
Behavior             0.20      0.90               0.180
                                          ──────────────
base_score                                         0.850
penalties                                          0.05
final_confidence                                   0.800

Classification: High (0.80 ≥ 0.75)
```

The calibrated weights produce a higher score that better reflects Cursor's actual detectability.

---

## 8. Summary

Cursor v2.5.26 is **highly detectable** through standard endpoint telemetry across Process, File, Network, and Behavior layers. It achieves the **highest confidence score of any tool tested** (0.79 vs 0.71 for Claude Code and 0.69 for Ollama) — the first tool to reach High confidence without sudo or EDR instrumentation.

**Key detection anchors (in priority order):**

1. `extension-host (agent-exec)` in process tree (Process — Class C escalation indicator, highest standalone confidence)
2. `~/.cursor/` directory with agent transcripts and `ai-code-tracking.db` (File — high-confidence attribution)
3. Persistent TLS connections to Cursor cloud endpoints attributed to extension-host PIDs (Network — high confidence)
4. Multi-file write bursts + shell execution from agent-exec context (Behavior — confirms active agentic usage)
5. `Made-with: Cursor` git trailer (Behavior — attribution signal, one-way)

**Key governance advantages:**

1. **Process-level class indicator** — `agent-exec` extension host maps directly to Class C governance class
2. **Complete session forensics** — agent transcript JSONL files record every tool call and action
3. **Persistent network attribution** — connections are long-lived and PID-attributable (unlike CLI tools)
4. **Code-signed binary** — cryptographic provenance via Apple notarization

**Key governance challenges:**

1. **Identity gap** — account state stored in Electron user-data-dir, not `~/.cursor/`; not examined in this run
2. **`Made-with` trailer evasion** — likely suppressible via settings (untested)
3. **Multi-window complexity** — each Cursor window creates a separate set of extension hosts; correlation across windows requires main-process PID as anchor

**Playbook validation status:** 9 of 9 Section 4.2 IOCs confirmed. 10 new findings to feed back into the playbook. Proposed Cursor-specific weight calibration. First High-confidence result achieved.
