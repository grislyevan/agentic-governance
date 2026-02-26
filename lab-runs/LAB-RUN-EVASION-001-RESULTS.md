# LAB-RUN-EVASION-001: Co-Authored-By Trailer Evasion Test

**Run ID:** LAB-RUN-EVASION-001  
**Date:** 2026-02-26  
**Tool:** Claude Code v2.1.59  
**Target IOC:** `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>` git trailer  
**Platform:** macOS 25.3.0 (ARM64), git 2.x  
**Prerequisite:** LAB-RUN-002 confirmed trailer presence under default configuration  

---

## Executive Summary

The `Co-Authored-By` git trailer is **trivially suppressible** through at least six independent evasion vectors. While it remains a high-value detection signal when present (near-zero false positives), its **absence is not probative** — a missing trailer does not indicate absence of AI involvement. Any detection strategy that relies on this trailer as a primary signal must account for the fact that a minimally sophisticated user can eliminate it with zero trace.

**Bottom line:** High-confidence *when present*, zero-confidence *when absent*. This is a one-way signal.

---

## Test Battery

### Test 1: Default Behavior (Baseline)

**Method:** Created a commit with Claude Code's exact trailer format.  
**Result:** Trailer present in commit message and visible via `git log --format="%B"`.

```
Test 1: default co-author behavior

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**Verdict:** CONFIRMED — trailer is present under default configuration.  
**Detection:** `git log --format="%B" | grep "Co-Authored-By:.*anthropic"` succeeds.

---

### Test 2: Settings-Based Suppression (Claude Code Native)

**Method:** Source code analysis of `cli.js` (minified) + official documentation + community reports.

**Finding:** Claude Code provides **two** documented mechanisms to suppress the trailer:

1. **`includeCoAuthoredBy: false`** in settings JSON  
2. **`attribution.commit: ""`** (empty string) in settings JSON  

Settings can be placed at three levels:
- `~/.claude/settings.json` (global — affects all repos)
- `.claude/settings.json` (project — shared via VCS)
- `.claude/settings.local.json` (local — gitignored, invisible to team)

**Empirical verification:** Blocked by Claude Code auth/workspace trust issues in non-interactive shell mode. However, the setting is confirmed via:
- String `Co-Authored-By` found in `cli.js` with surrounding attribution logic
- Official docs at `code.claude.com/docs/en/settings` document the setting
- Multiple independent community confirmations

**Verdict:** EVASION CONFIRMED (source + docs). User sets one config value and the trailer never appears.  
**Effort:** ~5 seconds (edit one JSON file).  
**Detectability of evasion:** None. The setting leaves no forensic trace.

---

### Test 3: Post-Commit Amend

**Method:** Created commit with trailer, then ran `git commit --amend -m "new message"`.

**Before:**
```
Test 3: commit with trailer (pre-amend)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

**After:**
```
Test 3: commit with trailer stripped via amend
```

**Verdict:** EVASION SUCCEEDED  
**Effort:** Single command.  
**Detectability:** The original commit hash changes (SHA rewrite). If the commit was already pushed, this requires a force-push which is detectable. If done before push, no trace remains.  
**Note:** Cursor re-injected its own `Made-with: Cursor` trailer during amend, but the Co-Authored-By trailer was not re-added (Claude Code was not involved in the amend operation).

---

### Test 4: Interactive Rebase

**Method:** Created commit with trailer, then used `git rebase -i HEAD~1` with automated `reword`.

**Before:** Trailer present, hash `461ff8a`.  
**After:** Trailer absent, hash `b6b55ec` (new commit object).

**Verdict:** EVASION SUCCEEDED  
**Effort:** Standard git rebase workflow.  
**Detectability:** Same as amend — hash changes. Detectable only if pre-rebase state was captured externally.

---

### Test 5: Local commit-msg Hook (Silent Stripping)

**Method:** Installed a `.git/hooks/commit-msg` hook that strips `Co-Authored-By:` lines before the commit object is created.

```bash
#!/bin/bash
TEMP_FILE=$(mktemp)
grep -v "^Co-Authored-By:" "$1" > "$TEMP_FILE"
sed -e :a -e '/^\n*$/{$d;N;ba' -e '}' "$TEMP_FILE" > "$1"
rm -f "$TEMP_FILE"
exit 0
```

**Result:** Claude Code generates the trailer, git passes it through the hook, the hook strips it, and the commit is created without the trailer. The trailer **never enters the object store**.

**Verdict:** EVASION SUCCEEDED — **most dangerous vector**  
**Effort:** One-time 6-line script.  
**Detectability:** The hook file itself (`.git/hooks/commit-msg`) is detectable by endpoint agents. However:
- The hook is not committed to the repo (it's in `.git/`, which is never tracked)
- The hook could be named anything if using `core.hooksPath`
- The hook's effect (absence of trailer) is indistinguishable from a tool that never added the trailer

---

### Test 6: filter-branch (Bulk History Rewrite)

**Method:** Ran `git filter-branch --msg-filter 'grep -v "^Co-Authored-By:"' -- --all` to strip trailers from the entire repository history.

**Before:** 1 commit with trailer in 5-commit history.  
**After (+ ref cleanup + gc):** 0 commits with trailer. All original commit objects garbage-collected.

**Verdict:** EVASION SUCCEEDED — complete history erasure  
**Effort:** Single command + cleanup.  
**Detectability:** All commit hashes change. Anyone with a copy of the original history (remote, CI cache, code review tool) could detect the rewrite by hash comparison. However, if done before the first push, no external record exists.

---

### Test 7: Global Git Template Hook

**Method:** Created a git template directory with a `commit-msg` hook and configured `init.templatedir`. All new repositories (and re-initialized repos) inherit the hook automatically.

**Result:** Same as Test 5 — trailer silently stripped. But now it applies to **every repository** the user creates or clones, automatically and invisibly.

**Verdict:** EVASION SUCCEEDED  
**Effort:** One-time global setup.  
**Detectability:** `git config --global init.templatedir` is readable by endpoint agents. The template directory and its hooks are detectable via filesystem scan.

---

### Test 8: Server-Side Hook (Defense Simulation)

**Method:** Set up a bare repository with a `pre-receive` hook that audits incoming commits for AI attribution trailers. Pushed the post-evasion history.

**Result:** All 6 commits arrived at the server with **no AI attribution detected**. The server-side hook correctly reported `⚠ No AI attribution detected` for every commit, but had no way to determine whether AI was involved.

**Verdict:** Server-side hooks **cannot recover stripped trailers**. They can only audit what the client sends. If the trailer was removed locally, the server sees the clean version.

---

## Evasion Vector Summary Matrix

| # | Vector | Succeeds? | Effort | Pre-Push Only? | Leaves Trace? | Detection Counter |
|---|---|---|---|---|---|---|
| 2 | Claude Code settings | ✓ Yes | ~5 sec | N/A (never created) | No | Scan for `includeCoAuthoredBy: false` or `attribution.commit: ""` in settings files |
| 3 | `git commit --amend` | ✓ Yes | ~5 sec | Best before push | Hash change | Compare pre/post push hashes; reflog analysis on endpoint |
| 4 | `git rebase -i` | ✓ Yes | ~30 sec | Best before push | Hash change | Same as amend |
| 5 | `commit-msg` hook | ✓ Yes | ~60 sec setup | N/A (never created) | Hook file on disk | Scan `.git/hooks/` and `core.hooksPath` for trailer-stripping patterns |
| 6 | `git filter-branch` | ✓ Yes | ~30 sec | Works on any history | All hashes change | Hash mismatch with any external copy |
| 7 | Global template hook | ✓ Yes | ~120 sec setup | N/A (never created) | Template dir + global config | Scan `init.templatedir` config + template hook files |

**Every tested evasion vector succeeded.**

---

## Implications for the Playbook

### 1. Trailer Signal Classification

The `Co-Authored-By` trailer must be reclassified from a potential "single strongest detection rule" to:

> **High-confidence positive signal / zero-confidence negative signal**  
> When present: near-certainty of AI involvement (specificity ≈ 1.0).  
> When absent: no inference possible (sensitivity ≈ 0 against motivated actor).

This is analogous to a confession in criminal law — extremely probative when obtained, but its absence proves nothing.

### 2. Defense-in-Depth Requirements

Relying on the Co-Authored-By trailer alone is insufficient. The detection strategy must combine:

1. **Trailer presence** (opportunistic — catches unaware/compliant users)
2. **Settings file scanning** (catches configuration-based suppression)
3. **Git hook auditing** (catches automated stripping)
4. **Cross-layer correlation** (file artifacts, process telemetry, network patterns — catches everything else)

### 3. New Evasion IOCs to Add to Section 4.1

| Layer | Evasion Indicator | What It Means | Confidence |
|---|---|---|---|
| File | `includeCoAuthoredBy: false` or `attribution.commit: ""` in any `settings.json` / `settings.local.json` | Deliberate suppression of AI attribution | High (intent signal) |
| File | `.git/hooks/commit-msg` containing `Co-Authored-By` or `grep -v` patterns | Automated trailer stripping | High (intent signal) |
| File | `git config --global init.templatedir` pointing to directory with trailer-stripping hooks | Systematic evasion across all repositories | Very High (intent signal) |
| Behavior | Commit history with hash discontinuities (force-push after amend/rebase/filter-branch) | Possible post-hoc trailer removal | Medium (many legitimate reasons for rebase) |

### 4. Recommended Enforcement Rule

```
Rule E1 — Co-Authored-By Evasion Detection
IF (Claude Code process detected OR ~/.claude/ directory present)
AND (settings file contains includeCoAuthoredBy: false OR attribution.commit: "")
OR (commit-msg hook contains Co-Authored-By stripping pattern)
THEN
  Confidence += 0.15 (evasion intent signal)
  Enforcement: Escalate to "Approval Required" 
  Alert: "AI attribution suppression detected — possible policy evasion"
```

### 5. "Git Audit" Module Implications

A standalone git audit module (scanning repos for AI co-author trailers) remains valuable but must be marketed with correct expectations:

- **What it catches:** Unaware users, compliant organizations, repos with mixed awareness
- **What it misses:** Any user who spends 5 seconds editing a settings file
- **Recommended positioning:** First-pass visibility tool, not a compliance gate
- **Must be combined with:** Endpoint telemetry for complete coverage

---

## Evidence Artifacts

| File | Content |
|---|---|
| `/Users/echance/claude-evasion-test/` | Full test repository with all evasion test commits |
| `/Users/echance/claude-evasion-test-remote.git/` | Bare repo showing server-side audit results |
| This document | Complete test methodology and findings |

---

## Confidence Score Impact

The evasion findings do **not** reduce the overall Claude Code detection confidence (0.77 from LAB-RUN-002). The Co-Authored-By trailer was a bonus signal on top of the multi-layer detection framework. The framework's core architecture — which doesn't depend on any single signal — is validated by this finding: even when one high-value signal is trivially evadable, the other layers maintain detection capability.

However, the **git audit module** as a standalone product must carry an explicit caveat: it provides visibility, not assurance.

---

*End of LAB-RUN-EVASION-001 — 2026-02-26*
