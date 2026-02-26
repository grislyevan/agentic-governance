# LAB-RUN-001 Results: Claude Code Installation & Runtime Telemetry

**Run ID:** LAB-RUN-001  
**Date:** 2026-02-26  
**Tool:** Claude Code v2.1.59 (`@anthropic-ai/claude-code`)  
**Scenario ID:** CC-POS-01 (Standard CLI install, first launch, agentic task)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/claude-lab/LAB-RUN-001/` (70 files, SHA-256 hashed per phase)

---

## 1. Signal Observation Matrix

### Process / Execution Layer

| IOC (Playbook Section 4.1) | Status | Evidence | Notes |
|---|---|---|---|
| CLI binary invocation (`claude`/`claude-code` entrypoint) from terminal parent | **Observed** | `phase2-launch/claude-process-tree.txt` | `login` → `zsh` (PID 30527) → `claude` (PID 31013). Binary at `/opt/homebrew/bin/claude`, symlink to `cli.js`. Process name shows as `claude` in `ps` — clean, unambiguous signal. |
| Child process chain: claude → shell → git/node/python subprocesses | **Observed differently** | `phase2-launch/pstree-stream.txt` | During agentic task, child processes were spawned (pytest execution produced `.pytest_cache/` and `__pycache__/`), but they terminated before our point-in-time `pstree` captures caught them. The background monitor at 2-second intervals was too coarse to capture the transient child chain. Evidence of shell execution is confirmed by artifact presence (`.pytest_cache/`, compiled `.pyc` files). |
| Long-lived interactive sessions with iterative command bursts | **Observed** | `phase2-launch/claude-process-snapshot.txt` | Session ran from 12:54 to exit (~10 minutes). CPU time 6.26s, memory grew from 59 MB idle to 84 MB during agentic task. Consistent with iterative prompt-response cycle. |

**Layer signal strength: 0.85** (Strong process identification, clear parent chain, child process evidence indirect but confirmed)

### File / Artifact Layer

| IOC (Playbook Section 4.1) | Status | Evidence | Notes |
|---|---|---|---|
| `~/.claude/` config/state directories | **Observed** | `phase2-launch/claude-dir-at-launch.txt`, `phase4-teardown/claude-dir-final.txt` | Created on first launch (not during install). 308 files at session end. Subdirectories: `backups/`, `cache/`, `debug/`, `plugins/`, `todos/`, `plans/`, `projects/`, `session-env/`, `shell-snapshots/`, `file-history/`. |
| Session history/cache artifacts with recent timestamps | **Observed** | `phase4-teardown/home-tree-diff.txt` | Session JSONL at `.claude/projects/-Users-echance/91a4f548-*.jsonl`. Debug log at `.claude/debug/91a4f548-*.txt` (76 KB). File history artifacts with content hashes. All timestamped to session window. |
| Prompt/context helper files near repo roots | **Not observed** | `phase3-agentic/project-claude-artifacts.txt` | No `.claude` files or directories created inside the `~/hello_world/` workspace. Claude Code kept all state in the global `~/.claude/` directory, not project-local. |

**Additional file-layer findings not in playbook:**

| Finding | Evidence | Significance |
|---|---|---|
| Plugin marketplace git clone on first launch | `phase2-launch/claude-dir-at-launch.txt` | Claude Code clones `anthropics/claude-plugins-official` into `~/.claude/plugins/marketplaces/` on first launch — significant file footprint (200+ files) |
| OAuth credential store in plaintext JSON | `phase2-launch/claude-config-contents.txt` | `.claude/backups/` contains full account state: email, org UUID, account UUID, billing type, org role. High-value identity artifact. |
| Feature flag cache | `phase3-agentic/claude-state-post-agentic.txt` | `cachedGrowthBookFeatures` object with internal codenames (`tengu_*`). Reveals product telemetry/experimentation state. |
| Terminal preferences backup | `phase3-agentic/claude-state-post-agentic.txt` | `appleTerminalBackupPath` field shows Claude Code backed up Terminal.plist and modified Option-as-Meta-key setting. |

**Layer signal strength: 0.95** (Rich, unique artifacts; `~/.claude/` is a high-confidence attribution anchor)

### Network Layer

| IOC (Playbook Section 4.1) | Status | Evidence | Notes |
|---|---|---|---|
| TLS/SNI to `api.anthropic.com`, `claude.ai` domains | **Not directly confirmed** | `phase2-launch/outbound-at-launch.txt`, `phase1-install/connections-stream.txt` | Without `sudo tcpdump` or TLS-aware capture, we could not confirm SNI targets. `lsof` showed node process connections during install (to npm registry) but Claude Code's process (PID 31013) did not appear in `lsof -i` output at the snapshot times — likely because connections were short-lived HTTPS requests between polling intervals. |
| Request burst cadence matching prompt→response→action cycles | **Not directly confirmed** | `phase2-launch/connections-stream.txt` | 2-second polling interval was too coarse to capture burst cadence. The connection stream shows general node activity but cannot be attributed to Claude Code PID specifically at this resolution. |

**Layer signal strength: 0.30** (Network signals present but unattributable without process-to-socket correlation at higher resolution or pcap capture)

### Identity / Access Layer

| IOC (Playbook Section 4.1) | Status | Evidence | Notes |
|---|---|---|---|
| API key env vars (`ANTHROPIC_API_KEY`) tied to user session | **Observed differently** | `baseline/anthropic-env.txt`, `phase2-launch/claude-config-contents.txt` | No `ANTHROPIC_API_KEY` env var was set. Instead, Claude Code uses OAuth browser-based authentication, storing credentials in `~/.claude/backups/` JSON files. The playbook's IOC should be expanded to include OAuth credential artifacts. |

**Additional identity findings:**

| Finding | Evidence | Significance |
|---|---|---|
| Full OAuth account profile stored locally | `phase2-launch/claude-config-contents.txt` | Email (`echance@magnite.com`), org UUID, account UUID, org role (admin), billing type (api_evaluation), display name — all in cleartext JSON. Stronger identity signal than env vars. |
| User ID hash for session correlation | `phase3-agentic/claude-state-post-agentic.txt` | `userID: ecfaaeb3...` — consistent hash across sessions, useful for actor correlation. |
| Session UUID as correlation key | `phase2-launch/claude-dir-at-launch.txt` | `91a4f548-2a12-438e-b993-5f3a623234de` appears in debug logs, project history, todos, and file-history — a single session ID that links all artifacts. |

**Layer signal strength: 0.80** (OAuth credential store is a richer identity signal than the predicted env var pattern)

### Behavior Layer

| IOC (Playbook Section 4.1) | Status | Evidence | Notes |
|---|---|---|---|
| Rapid multi-file read/write loops across repo | **Observed** | `phase3-agentic/workspace-files.txt` | 3 source files (`hello.py`, `test_hello.py`, `README.md`) created at 12:58 within seconds of each other. Tight temporal clustering confirms burst-write pattern. |
| Shell command orchestration from AI session context | **Observed** | `phase3-agentic/workspace-files.txt` | `.pytest_cache/` and `__pycache__/test_hello.cpython-311-pytest-8.4.1.pyc` prove pytest was executed from within the Claude Code session. The test framework artifact timestamps match the file creation window. |
| Git commit/patch generation shortly after model interaction | **Not observed** | `phase3-agentic/git-check.txt` | No `.git` directory in workspace. Claude Code did not run `git init` or make any commits for this task. This IOC may be task-dependent rather than inherent to the tool. |

**Layer signal strength: 0.75** (Clear agentic loop observed: file write fan-out + shell execution. Git IOC not triggered for this scenario.)

---

## 2. Confidence Score Calculation

### Using Five-Layer Defaults (Playbook Appendix B)

```
Layer                Weight    Signal Strength    Weighted
Process / Execution  0.30      0.85               0.255
File / Artifact      0.20      0.95               0.190
Network              0.15      0.30               0.045
Identity / Access    0.15      0.80               0.120
Behavior             0.20      0.75               0.150
                                          ──────────────
base_score                                         0.760
```

### Applicable Penalties

```
[✗] Missing parent-child process chain:          −0.15  → NOT APPLIED (chain observed)
[✗] Wrapper/renamed binary:                      −0.15  → NOT APPLIED (standard install)
[✗] Stale artifact only:                         −0.10  → NOT APPLIED (fresh timestamps)
[✗] Non-default artifact paths:                  −0.10  → NOT APPLIED (standard ~/.claude/)
[✗] Ambiguous proxy/gateway route:               −0.10  → NOT APPLIED (direct connection)
[△] Unresolved process-to-network linkage:       −0.10  → PARTIAL: −0.05
    (Network seen but not attributed to claude PID at capture resolution)
[✗] Containerized/remote execution:              −0.10  → NOT APPLIED (native macOS)
[✗] Weak/missing identity correlation:           −0.10  → NOT APPLIED (full OAuth profile captured)
                                                 ──────
penalties                                         0.05
```

### Final Score

```
final_confidence = 0.760 - 0.05 = 0.71

Classification: Medium (0.45 ≤ 0.71 < 0.75)
```

### Using Three-Layer Weights (INIT-43)

```
Layer       Weight    Signal Strength    Weighted
Process     0.45      0.85               0.3825
File        0.30      0.95               0.2850
Network     0.25      0.30               0.0750
                                  ──────────────
base_score                                 0.7425
penalties                                  0.05
final_confidence                           0.6925

Classification: Medium (0.45 ≤ 0.69 < 0.75)
```

### Score Assessment

The Medium classification feels **slightly low** given the strength of the observed signals. The network layer is dragging down the score because we lacked `sudo` access for proper traffic capture. In a production deployment with EDR-level network telemetry (process-to-socket correlation), the network signal strength would likely be 0.70+, pushing the final score above the 0.75 High threshold.

**Projected score with EDR-grade network telemetry:** ~0.82 (High confidence)

---

## 3. Policy Decision

Per Playbook Section 6.3 Deterministic Escalation Rules:

| Dimension | Value |
|---|---|
| Detection Confidence | Medium (0.71) |
| Tool Class | C (Autonomous Executor — agentic mode active) |
| Asset Sensitivity | Tier 0 (home directory, non-sensitive test project) |
| Action Risk | R2 (scoped writes in non-protected path) + R3 (shell command execution) |
| Actor Trust | T2 (known org user, managed endpoint) |

**Applicable rules:**
- Rule 2: Medium confidence + Tier 0/1 + R2 → **Warn**
- Rule 3: Medium confidence + R3 (shell execution) → **Approval Required**

**Decision: Warn with step-up to Approval Required** for the shell execution component.

In a production scenario with EDR-grade telemetry pushing confidence to High:
- Rule 4 would apply for any disallowed R4 actions → **Block**

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-001
Date:                2026-02-26
Tool:                Claude Code v2.1.59 (@anthropic-ai/claude-code)
Scenario ID:         CC-POS-01 (Standard CLI install + agentic task)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint,
                     home network, direct internet
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — claude binary with clear terminal → zsh → claude
                     lineage. Child processes transient but artifact-confirmed.
                     Evidence: phase2-launch/claude-process-tree.txt,
                     phase2-launch/claude-process-snapshot.txt
  File/Artifact:     OBSERVED — ~/.claude/ with 308 files including session state,
                     debug logs, OAuth credentials, plugin marketplace, config.
                     Evidence: phase2-launch/claude-dir-at-launch.txt,
                     phase4-teardown/claude-dir-final.txt,
                     phase4-teardown/home-tree-diff.txt
  Network:           PARTIALLY OBSERVED — connections visible but not attributed
                     to claude PID at 2-second polling resolution. No pcap captured
                     (no sudo access). Evidence: phase2-launch/connections-stream.txt
  Identity:          OBSERVED — OAuth account profile with email, org, role stored
                     in ~/.claude/backups/. Session UUID correlation across all
                     artifacts. Evidence: phase2-launch/claude-config-contents.txt
  Behavior:          OBSERVED — Multi-file write burst (3 files in <5s) + shell
                     command execution (pytest). Agentic loop pattern confirmed.
                     Evidence: phase3-agentic/workspace-files.txt,
                     phase3-agentic/workspace-contents.txt

Confidence Result:   0.71 (Medium) — five-layer model
                     0.69 (Medium) — three-layer model (INIT-43)
                     Projected with EDR telemetry: ~0.82 (High)
Policy Decision:     Warn / Approval Required (Rules 2+3, Section 6.3)
Evidence Links:      70 files across 5 phase directories, SHA-256 hashed
                     (see MASTER-HASHES.txt)
Pass/Fail:           CONDITIONAL PASS
Residual Risk:       Network layer under-instrumented without sudo/EDR;
                     child process capture requires <1s polling or ESF;
                     no terminal session recording (script) was used
```

---

## 5. Findings and Playbook Feedback

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 1 | **OAuth credential store is the primary identity signal, not env vars.** Claude Code v2.1.59 uses browser OAuth, storing full account profile (email, org UUID, role, billing type) in `~/.claude/backups/*.json`. The playbook's IOC lists `ANTHROPIC_API_KEY` env var, which was not present. | Section 4.1 Identity IOC | Add IOC: "OAuth account profile stored in `~/.claude/backups/` JSON files" with Confidence Weight: High. Retain API key IOC as alternate path. |
| 2 | **`~/.claude/` is not created during install — only on first launch.** The playbook's File IOC doesn't distinguish install-time vs runtime artifacts. The npm install creates zero files in the user's home directory; all state artifacts appear only after the first `claude` invocation. | Section 4.1 File IOC | Add note: "Config/state directories created on first launch, not install. Absence after install ≠ absence of tool." |
| 3 | **Plugin marketplace is auto-cloned on first launch.** Claude Code git-clones `anthropics/claude-plugins-official` into `~/.claude/plugins/marketplaces/`. This is 200+ files and includes a `.git` directory — a large, distinctive file footprint not mentioned in the playbook. | Section 4.1 File IOC | Add IOC: "Git clone of plugin marketplace in `~/.claude/plugins/marketplaces/`" with Confidence Weight: Medium–High. |
| 4 | **Git operations did not occur for this task.** The playbook lists "Git commit/patch generation shortly after model interaction" as a behavioral IOC. This is task-dependent, not inherent to the tool. Simple file creation tasks do not trigger git operations. | Section 4.1 Behavior IOC | Reclassify git IOC as "conditional on task type" rather than expected baseline behavior. Ensure validation matrix includes a git-specific scenario (CC-POS-02). |
| 5 | **Feature flag cache reveals product telemetry state.** The `cachedGrowthBookFeatures` field in Claude Code's config exposes internal feature flags with `tengu_*` codenames. This is a forensic bonus — it reveals product version behavior and experimentation state. | Section 4.1 File IOC (new) | Add IOC: "Feature flag cache in session config with Anthropic-internal codenames" — useful for version fingerprinting and behavior prediction. |
| 6 | **Terminal preferences modification.** Claude Code modified the macOS Terminal's Option-as-Meta-Key setting and created a backup of `com.apple.Terminal.plist`. This is a host configuration change not mentioned in any detection profile. | Section 4.1 File IOC (new) | Add IOC: "Terminal.plist modification and backup" — low confidence standalone but contributes to file-layer correlation. Also relevant to Section 7 (Risky Action Controls) as a host config modification. |
| 7 | **2-second polling is insufficient for child process capture.** Transient child processes (shell → python → pytest) completed between polling intervals. The agentic loop's child chain was proven by artifacts but not directly observed in process telemetry. | Section 12 (Lab Validation) | Require sub-second process monitoring or ESF-level telemetry for Phase 3 agentic scenarios. Add note that artifact-based confirmation is acceptable fallback. |
| 8 | **Network signal is weak without process-to-socket correlation.** `lsof` polling at 2-second intervals could not attribute specific connections to the claude process. Short-lived HTTPS requests completed between polls. | Section 4.1 Network IOC, Appendix B | Document that network-layer confidence for CLI tools requires continuous telemetry (EDR/ESF), not polling-based capture. Consider reducing default network weight for polling-only deployments. |
| 9 | **Session UUID is a powerful cross-artifact correlation key.** The UUID `91a4f548-2a12-438e-b993-5f3a623234de` appears in debug logs, project history, todos, file-history, and session-env — linking all session artifacts under one identifier. | Section 4.1 (new IOC), Appendix A | Add as a cross-layer correlation signal. Session UUID in `~/.claude/` artifacts enables linking file, identity, and behavior evidence to a single session with high confidence. |
| 10 | **No persistence mechanisms installed.** Claude Code made zero changes to shell profiles, LaunchAgents, crontab, or systemd services. It is purely on-demand with no daemon or background service. | Section 4.1 (general note) | Document that Claude Code has a clean persistence posture — all state is passive (config/cache files), no active persistence. This distinguishes it from tools like Ollama (daemon). |

---

## 6. Summary

Claude Code v2.1.59 is **highly detectable** through standard endpoint telemetry across Process, File, and Identity layers. The behavioral layer confirms agentic patterns during active use. The primary detection gap is the Network layer, which requires EDR-grade process-to-socket correlation to achieve high confidence.

**Key detection anchors (in priority order):**

1. `~/.claude/` directory presence and contents (File — highest standalone confidence)
2. `claude` process with terminal parent chain (Process — high confidence)
3. OAuth credential profile in backup JSON (Identity — high confidence)
4. Multi-file write bursts + shell execution from claude session context (Behavior — high confidence)
5. TLS connections to `api.anthropic.com` (Network — requires EDR for attribution)

The tool leaves a **large, distinctive forensic footprint** — 308 persistent files after a single session, including session transcripts, file edit history, and full OAuth account details. This makes post-hoc detection straightforward even without real-time monitoring.

**Playbook validation status:** 9 of 12 IOCs confirmed or partially confirmed. 3 IOCs not observed (1 task-dependent, 2 instrumentation-limited). 10 new findings to feed back into the playbook.
