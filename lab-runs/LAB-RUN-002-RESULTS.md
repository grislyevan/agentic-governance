# LAB-RUN-002 Results: Claude Code Git-Heavy Agentic Task + Terminal Recording

**Run ID:** LAB-RUN-002  
**Date:** 2026-02-26  
**Tool:** Claude Code v2.1.59 (`@anthropic-ai/claude-code`)  
**Scenario ID:** CC-POS-02 (Multi-module project + git operations + test execution)  
**Environment:** macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2), managed endpoint  
**Scenario Type:** Positive  
**Evidence Directory:** `~/claude-lab/LAB-RUN-002/` (33 files, SHA-256 hashed per phase)  
**Predecessor:** LAB-RUN-001 (this run targets three specific gaps from RUN-001)

---

## 1. Gaps Targeted

| Gap from RUN-001 | Resolution | Status |
|---|---|---|
| No terminal session recording | `script` captured 5,629-line / 237 KB terminal log | **Closed** |
| Git IOC not observed (task-dependent) | Git-heavy task triggered `git init` + `git add` + `git commit` | **Closed** |
| 2-second process polling missed child chains | 500ms filtered polling captured `claude` → `zsh` → `bash` → `python` chain | **Closed** |

---

## 2. Key Findings

### Finding 1: Git IOC Confirmed — with Co-Authored-By Attribution Trailer

Claude Code executed the full git lifecycle:

```
git init → file creation (6 files) → pytest execution → git add → git commit
```

**Critical discovery:** The commit includes a `Co-Authored-By` trailer:

```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

This is a **high-confidence, near-zero-false-positive attribution signal**. It is:
- Embedded in git history (persistent, forensically durable)
- Machine-readable (trivially detectable with `git log --format='%b' | grep 'Co-Authored-By.*anthropic'`)
- Includes the model version (`Claude Sonnet 4.6`) — useful for fingerprinting
- Present in the commit metadata, not just the diff

**Recommended detection rule:** Scan git commit trailers for `Co-Authored-By:.*anthropic\.com` across all monitored repositories. This alone is sufficient for high-confidence attribution without any process or network telemetry.

**Evidence:** `phase2-agentic/git-log.txt`, `phase2-agentic/commit-message.txt`

### Finding 2: Child Process Chain Captured at 500ms

The filtered 500ms polling successfully captured the process chain:

```
claude (PID 42510)
├── /bin/zsh (PID 43061)        ← shell spawned for command execution
│   ├── bash (PID 43063)        ← git operations
│   └── bash (PID 43420)        ← additional commands
├── /bin/zsh (PID 44022)        ← second shell session
│   └── python (PID 44024)      ← pytest execution
│       └── bash (PID 44034)    ← python subprocess
├── npm view @anthropic-ai/claude-code@latest version (PID 43700, 43886, 44021)
│                               ← version check against registry (3 attempts)
└── [transient git processes — too fast even at 500ms]
```

Git processes (`git init`, `git add`, `git commit`) were still too transient to capture at 500ms — they completed in <500ms. However, the `bash` processes that executed them (PIDs 43063, 43420) were captured. This confirms the process chain `claude` → `zsh` → `bash` → `git` even without catching `git` directly.

**Methodology note:** Capturing `git` processes directly would require ESF (`eslogger exec`) or ≤100ms polling. For practical detection, the parent chain (`claude` → `zsh` → `bash`) combined with git artifact evidence (`.git/` directory, commit log) is sufficient.

**Evidence:** `phase2-agentic/claude-child-chains.txt`, `phase2-agentic/full-process-chain.txt`, `phase1-launch/pstree-stream.txt`

### Finding 3: Terminal Session Fully Recorded

The `script` session log (237 KB, 5,629 lines) captured the complete interactive session including:
- Authentication flow
- Task prompt entry
- Permission dialogs (Claude Code asking to run `git init`, create files)
- Tool execution output (`git init` output, pytest results)
- Commit generation

The log contains ANSI escape sequences (terminal formatting) which need stripping for clean analysis, but the raw data preserves exact timing and sequence of all operations.

**Evidence:** `phase1-launch/terminal-session.log`

### Finding 4: Claude Code Checks for Updates During Session

The process monitor captured three `npm view @anthropic-ai/claude-code@latest version` calls during the session. This is Claude Code checking for newer versions — a network-layer signal not documented in the playbook. These are outbound calls to the npm registry, attributable to the `claude` PID.

**Evidence:** `phase2-agentic/unique-child-processes.txt`

### Finding 5: Git Author Identity

The commit author is `ziltoidiaAttax <echance@magnite.com>` — Claude Code used the existing git config identity, not its own. The AI attribution is in the `Co-Authored-By` trailer only. This means:
- The human identity is the commit author (governance-appropriate)
- The AI identity is explicitly disclosed via trailer
- Detection can key on either: git author + trailer presence = AI-assisted commit

**Evidence:** `phase2-agentic/git-author.txt`

---

## 3. Updated Confidence Score

With the RUN-001 gaps closed, the confidence score improves:

```
Layer                Weight    Signal Strength    Weighted    Change from RUN-001
Process / Execution  0.30      0.90               0.270       ↑ (child chain captured)
File / Artifact      0.20      0.95               0.190       = (unchanged)
Network              0.15      0.35               0.053       ↑ (npm version check attributed)
Identity / Access    0.15      0.85               0.128       ↑ (git author + OAuth)
Behavior             0.20      0.90               0.180       ↑ (git IOC confirmed)
                                          ──────────────
base_score                                         0.820

Applicable penalties:
[△] Unresolved process-to-network linkage:  −0.05 (partial — API traffic still unattributed)

final_confidence = 0.820 - 0.05 = 0.77

Classification: HIGH (≥ 0.75)
```

With the git IOC confirmed and child process chain captured, Claude Code crosses the **High confidence threshold** even without EDR-grade network telemetry.

---

## 4. Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-002
Date:                2026-02-26
Tool:                Claude Code v2.1.59 (@anthropic-ai/claude-code)
Scenario ID:         CC-POS-02 (Multi-module + git + tests)
Environment:         macOS 26.3, Darwin 25.3.0, ARM64 (M2), managed endpoint
Scenario Type:       Positive

Signal Observations:
  Process:           OBSERVED — claude → zsh → bash → python chain captured at
                     500ms polling. Git processes transient (<500ms) but parent
                     bash captured. npm version-check child processes attributed.
  File/Artifact:     OBSERVED — 6 source files, .git/ directory, pytest artifacts.
                     ~/.claude/ with session state.
  Network:           PARTIALLY OBSERVED — npm registry calls attributed to claude
                     PID. API traffic to anthropic still unattributed without pcap.
  Identity:          OBSERVED — Git author identity (ziltoidiaAttax/echance@magnite.com)
                     + Co-Authored-By trailer (Claude Sonnet 4.6) + OAuth profile.
  Behavior:          OBSERVED — Full agentic loop: file write fan-out (6 files) +
                     shell execution (pytest, 16 tests) + git operations
                     (init/add/commit) + AI co-author attribution.

Confidence Result:   0.77 (High) — five-layer model
Policy Decision:     Approval Required / Block (Rule 3/4, Section 6.3)
Evidence Links:      33 files, SHA-256 hashed (see MASTER-HASHES.txt)
Pass/Fail:           PASS
Residual Risk:       API traffic to anthropic still requires EDR for PID attribution.
                     Git processes require <100ms polling or ESF for direct capture.
```

---

## 5. Playbook Feedback (Incremental to RUN-001)

| # | Finding | Affected Section | Recommended Change |
|---|---|---|---|
| 11 | **`Co-Authored-By` trailer is the highest-confidence git-based attribution signal.** `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` in commit metadata. Near-zero false positive rate. Machine-readable, forensically durable, survives rebases. | Section 4.1 Behavior IOC | Add dedicated IOC for `Co-Authored-By:.*anthropic\.com` in git commit trailers. Confidence Weight: **Very High**. Consider adding to Appendix A as a standalone high-confidence attribution rule. |
| 12 | **Claude Code performs npm registry version checks during sessions.** Three `npm view @anthropic-ai/claude-code@latest version` calls observed. Attributable to claude PID. | Section 4.1 Network IOC | Add IOC: "Outbound `npm view` calls to registry for `@anthropic-ai/claude-code` version during active session." Confidence Weight: Medium. |
| 13 | **500ms polling captures parent shell chain but not transient git processes.** `git init/add/commit` complete in <500ms. Direct capture requires ESF or <100ms polling. Parent chain (bash) capture is sufficient fallback. | Section 12.4 Methodology | Update guidance: 500ms is adequate for shell/python chains but insufficient for git. Artifact-based + parent-chain confirmation is the practical standard. |
