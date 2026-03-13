# Lab Run Protocol: Claude Code Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-001  
**Tool:** Claude Code (`@anthropic-ai/claude-code`)  
**Class:** C (Autonomous Executor)  
**Playbook Reference:** Section 4.1 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**INIT-43 Reference:** [init-issues/INIT-43-claude-process-file-network-signal-map.md](../init-issues/INIT-43-claude-process-file-network-signal-map.md) — process/file/network signal map, normalization fields, failure modes, correlation rules C1–C4, validation plan. Lab outputs must satisfy INIT-43 required outputs (per-layer report, confidence trace, correlation rule evaluation, residual ambiguity).  
**Target Scenario:** Positive — Standard install, first launch, agentic task execution  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | Linux VPS (Ubuntu 22.04+ recommended) or macOS (native, not containerized) |
| **Node.js** | v18+ with npm |
| **Shell** | bash or zsh |
| **Root/sudo** | Required for `tcpdump` and `strace` (Linux) |
| **Disk** | Sufficient space for evidence artifacts (~500 MB headroom) |
| **Network** | Outbound internet access (npm registry, Anthropic API) |

### Tool Availability Check

Run before starting. All must be present:

```bash
node --version
npm --version
which tcpdump        # needs sudo
which strace         # Linux only; macOS uses dtrace/dtruss
which script         # terminal session recorder
which pstree         # process tree viewer (install: apt install psmisc / brew install pstree)
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/claude-lab/LAB-RUN-001
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3-agentic,phase4-teardown}
```

### INIT-43 Signal Map Alignment

Captures in this protocol map to INIT-43 normalization and correlation as follows:

| INIT-43 layer | Normalization fields (INIT-43) | Protocol capture |
|---------------|--------------------------------|------------------|
| **Process** | proc.path, parent_chain, child_chain, proc.signer | Phase 1: binary path, npm list, which claude, binary-metadata (hash). Phase 2: claude-process-tree, pstree-stream, claude-tree-idle, auth-processes. Phase 3: pstree-stream (1s), strace-agentic (clone/execve/openat/connect). |
| **File** | artifact.path, artifact.type, artifact.last_modified, artifact.repo_scope | Baseline: home-tree, claude-dir-check, claude-artifact-scan. Phase 1: new-files, claude-dir-post. Phase 2: new-files-at-launch, claude-dir-at-launch, claude-config-contents. Phase 3: workspace-files, workspace-contents, new-files-during-agentic, claude-dir-post-agentic. Phase 4: home-tree-diff, claude-dir-final, claude-artifacts-detail. |
| **Network** | net.dest_ip, net.conn_*, net.proc_link_confidence | Phase 1: install-traffic.pcap, dns-queries. Phase 2: launch-traffic.pcap, connections-stream, outbound-at-launch. Phase 3: agentic-traffic.pcap, connections-stream. (Process-to-socket linkage requires lsof -i per PID or EDR; 2s polling limits attribution.) |

Correlation rules C1–C4 (Appendix A) are evaluated in Phase 5. Penalties (INIT-43 Section 6, Appendix B): missing parent-child chain, wrapper/renamed binary, stale artifact only, non-default paths, ambiguous proxy, unresolved process–network linkage, containerized/remote execution, weak identity.

---

## Pre-Install: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer so each subsequent phase produces a meaningful diff.

### File System Baseline

```bash
# Home directory tree (depth-limited to keep it manageable)
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

# Specifically confirm no pre-existing Claude artifacts
ls -la ~/.claude 2>&1 > "$LAB_DIR/baseline/claude-dir-check.txt"
find ~ -name '*.claude*' -o -name '*anthropic*' 2>/dev/null \
  > "$LAB_DIR/baseline/claude-artifact-scan.txt"

# /tmp state
ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"

# Shell profile snapshots (detect later modifications)
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename $f).bak"
done
```

### Process Baseline

```bash
# Full process listing
ps auxww > "$LAB_DIR/baseline/ps-full.txt"

# Process tree
pstree -p > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || ps auxf > "$LAB_DIR/baseline/ps-tree.txt"
```

### Network Baseline

```bash
# Listening ports
ss -tlnp > "$LAB_DIR/baseline/listening-ports.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"

# Active outbound connections
ss -tnp > "$LAB_DIR/baseline/active-connections.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"
```

### Environment Baseline

```bash
# Full environment dump
env | sort > "$LAB_DIR/baseline/env-vars.txt"

# Anthropic-specific key check
env | grep -i anthropic > "$LAB_DIR/baseline/anthropic-env.txt" 2>/dev/null
echo "Exit code: $? (1 = no ANTHROPIC vars found, expected)" >> "$LAB_DIR/baseline/anthropic-env.txt"

# npm global packages
npm list -g --depth=0 > "$LAB_DIR/baseline/npm-globals.txt" 2>&1

# PATH check for claude
which claude > "$LAB_DIR/baseline/which-claude.txt" 2>&1
which claude-code >> "$LAB_DIR/baseline/which-claude.txt" 2>&1
echo "Exit code: $? (1 = not found, expected)" >> "$LAB_DIR/baseline/which-claude.txt"
```

### Persistence Mechanism Baseline

```bash
# Linux: systemd user services, crontab
systemctl --user list-units --type=service > "$LAB_DIR/baseline/user-services.txt" 2>/dev/null
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1

# macOS: LaunchAgents
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
```

### Create Baseline Timestamp Marker

```bash
touch "$LAB_DIR/baseline/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/baseline/start-time.txt"
```

### Hash All Baseline Evidence

```bash
shasum -a 256 "$LAB_DIR/baseline/"* > "$LAB_DIR/baseline/EVIDENCE-HASHES.txt"
```

---

## Phase 1: Installation — What Changes on Disk and Network

**Purpose:** Capture the full installation footprint — files created, network connections made, binaries placed, postinstall scripts executed.

### Start Background Monitors

Open separate terminals (or use `tmux`/`screen` panes):

```bash
# Terminal A: Network capture (requires sudo)
sudo tcpdump -i any -w "$LAB_DIR/phase1-install/install-traffic.pcap" &
TCPDUMP_PID=$!

# Terminal B: DNS query log
sudo tcpdump -i any port 53 -l 2>/dev/null | \
  tee "$LAB_DIR/phase1-install/dns-queries.txt" &
DNS_PID=$!

# Terminal C: Process monitor (snapshot every 2 seconds)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase1-install/ps-stream.txt"
  ps auxww >> "$LAB_DIR/phase1-install/ps-stream.txt"
  sleep 2
done &
PS_PID=$!
```

### Run Installation

```bash
# Capture full install output including any postinstall scripts
npm install -g @anthropic-ai/claude-code 2>&1 | \
  tee "$LAB_DIR/phase1-install/npm-install-output.txt"

echo "Install exit code: $?" >> "$LAB_DIR/phase1-install/npm-install-output.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $DNS_PID 2>/dev/null
sudo kill $TCPDUMP_PID 2>/dev/null
```

### Post-Install Capture

```bash
# Updated npm globals
npm list -g --depth=0 > "$LAB_DIR/phase1-install/npm-globals-post.txt" 2>&1

# Diff against baseline
diff "$LAB_DIR/baseline/npm-globals.txt" "$LAB_DIR/phase1-install/npm-globals-post.txt" \
  > "$LAB_DIR/phase1-install/npm-globals-diff.txt"

# Binary discovery
which claude > "$LAB_DIR/phase1-install/which-claude.txt" 2>&1
which claude-code >> "$LAB_DIR/phase1-install/which-claude.txt" 2>&1

# Explicit version capture (IOC profiles may differ across versions)
npm list -g @anthropic-ai/claude-code --json > "$LAB_DIR/phase1-install/claude-version.json" 2>&1

# Binary metadata and hash
CLAUDE_BIN=$(which claude 2>/dev/null || which claude-code 2>/dev/null)
if [ -n "$CLAUDE_BIN" ]; then
  ls -la "$CLAUDE_BIN" > "$LAB_DIR/phase1-install/binary-metadata.txt"
  file "$CLAUDE_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  readlink -f "$CLAUDE_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt" 2>/dev/null
  shasum -a 256 "$CLAUDE_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
fi

# New files since baseline marker
find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -not -path '*/claude-lab/*' \
  -not -path '*/.cache/*' \
  -not -path '*/node_modules/*' \
  2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt"

# Claude-specific artifact check
ls -laR ~/.claude 2>&1 > "$LAB_DIR/phase1-install/claude-dir-post.txt"

# Shell profile diff (did install modify PATH in dotfiles?)
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase1-install/shellprofile-diff-$base.txt" 2>&1
  fi
done

# Persistence mechanism check
crontab -l > "$LAB_DIR/phase1-install/crontab-post.txt" 2>&1
diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase1-install/crontab-post.txt" \
  > "$LAB_DIR/phase1-install/crontab-diff.txt" 2>&1
```

### Phase 1 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
shasum -a 256 "$LAB_DIR/phase1-install/"* > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 2: First Launch — Process Tree, Auth Flow, and Idle State

**Purpose:** Capture what happens when `claude` starts but before any agentic task — process lineage, authentication behavior, network connections at idle, and config/state file creation.

### Start Background Monitors

```bash
# Terminal A: Network capture
sudo tcpdump -i any -w "$LAB_DIR/phase2-launch/launch-traffic.pcap" &
TCPDUMP_PID=$!

# Terminal B: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/connections-stream.txt"
  ss -tnp >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null || \
    lsof -i -nP >> "$LAB_DIR/phase2-launch/connections-stream.txt"
  sleep 2
done &
CONN_PID=$!

# Terminal C: Process tree snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase2-launch/pstree-stream.txt" 2>/dev/null || \
    ps auxf >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!
```

### Start Terminal Session Recorder

```bash
# Records the full terminal session including all claude output
script -q "$LAB_DIR/phase2-launch/terminal-session.log"
```

> You are now inside `script`. Everything typed and displayed is recorded.

### Launch Claude Code

```bash
claude
```

### Capture During Auth/Login Flow

While Claude Code walks you through authentication, note in a separate terminal:

```bash
# Snapshot: what processes does claude spawn?
pstree -p $(pgrep -f claude | head -1) > "$LAB_DIR/phase2-launch/claude-process-tree.txt" 2>/dev/null

# Did it open a browser or spawn any child processes for auth?
ps auxww | grep -E 'claude|anthropic|open |xdg-open' > "$LAB_DIR/phase2-launch/auth-processes.txt"

# New listening ports?
ss -tlnp > "$LAB_DIR/phase2-launch/listening-ports-during-auth.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/phase2-launch/listening-ports-during-auth.txt"

# Outbound connections right now
ss -tnp > "$LAB_DIR/phase2-launch/outbound-at-launch.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/phase2-launch/outbound-at-launch.txt"
```

### Capture After Auth Completes (Idle at Prompt)

Once Claude Code is authenticated and sitting at its prompt, waiting for input:

```bash
# Process tree of claude and its children
pstree -p $(pgrep -f claude | head -1) > "$LAB_DIR/phase2-launch/claude-tree-idle.txt" 2>/dev/null

# New files created on first launch
find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -not -path '*/claude-lab/*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/new-files-at-launch.txt"

# Claude config/state directory contents
ls -laR ~/.claude > "$LAB_DIR/phase2-launch/claude-dir-at-launch.txt" 2>&1

# Environment variable access trace (Linux only, requires separate terminal with sudo)
# NOTE: Attaching strace with openat,read to a Node.js process produces extreme noise —
# Node reads hundreds of files during normal operation. Filter aggressively for
# anthropic/claude-specific paths, or limit capture to 10 seconds. On first runs,
# file-change diffs (Phase 4 home-tree-diff) are a more practical alternative.
sudo strace -p $(pgrep -f 'node.*claude' | head -1) -e trace=openat \
  -f -o "$LAB_DIR/phase2-launch/strace-launch.txt" &
STRACE_PID=$!
sleep 10 && sudo kill $STRACE_PID 2>/dev/null
# Post-filter for relevant paths:
# grep -E 'anthropic|claude|\.env|api.key' "$LAB_DIR/phase2-launch/strace-launch.txt" \
#   > "$LAB_DIR/phase2-launch/strace-filtered.txt"
```

### Permission Model Check

Before moving to Phase 3, document Claude Code's permission settings:

```bash
# Check for permission/settings config files
find ~/.claude -type f 2>/dev/null | while read f; do
  echo "=== $f ===" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt"
  cat "$f" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt" 2>/dev/null
  echo "" >> "$LAB_DIR/phase2-launch/claude-config-contents.txt"
done
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
sudo kill $TCPDUMP_PID 2>/dev/null
```

### Phase 2 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-launch/phase2-end-time.txt"
shasum -a 256 "$LAB_DIR/phase2-launch/"* > "$LAB_DIR/phase2-launch/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3: Agentic Session — Trigger Class C Behavioral Signals

**Purpose:** Validate the autonomous executor IOCs. Force Claude Code to read files, write multiple files, and execute shell commands — the agentic loop signature.

### Prepare a Clean Working Directory

```bash
mkdir -p ~/claude-lab-workspace && cd ~/claude-lab-workspace
```

### Start Background Monitors

```bash
# Terminal A: Full traffic capture
sudo tcpdump -i any -w "$LAB_DIR/phase3-agentic/agentic-traffic.pcap" &
TCPDUMP_PID=$!

# Terminal B: Process tree every 1 second (higher frequency for agentic bursts)
# WARNING: 1-second pstree polling generates large output (~300KB/min). This is
# intentional — transient child processes (claude → sh → python) only live for
# sub-second windows. Ensure analysis scripts can handle the volume. For smaller
# output, use: ps -eo pid,ppid,comm | grep -E 'claude|node|python|sh|git'
while true; do
  echo "=== $(date -u +%H:%M:%S.%N) ===" >> "$LAB_DIR/phase3-agentic/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase3-agentic/pstree-stream.txt" 2>/dev/null || \
    ps auxf >> "$LAB_DIR/phase3-agentic/pstree-stream.txt"
  sleep 1
done &
PS_PID=$!

# Terminal C: File change watcher on workspace
inotifywait -mr ~/claude-lab-workspace -o "$LAB_DIR/phase3-agentic/file-events.txt" \
  --format '%T %w%f %e' --timefmt '%H:%M:%S' 2>/dev/null &
INOTIFY_PID=$!
# macOS alternative: fswatch ~/claude-lab-workspace > "$LAB_DIR/phase3-agentic/file-events.txt" &

# Terminal D: Connection snapshots every 1 second
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-agentic/connections-stream.txt"
  ss -tnp >> "$LAB_DIR/phase3-agentic/connections-stream.txt" 2>/dev/null || \
    lsof -i -nP >> "$LAB_DIR/phase3-agentic/connections-stream.txt"
  sleep 1
done &
CONN_PID=$!

# Terminal E: strace on claude process (Linux only)
sudo strace -p $(pgrep -f 'node.*claude' | head -1) -e trace=clone,execve,openat,connect \
  -f -o "$LAB_DIR/phase3-agentic/strace-agentic.txt" &
STRACE_PID=$!
```

### Start Terminal Session Recorder (if not already running from Phase 2)

```bash
script -q "$LAB_DIR/phase3-agentic/terminal-session.log"
```

### Issue the Agentic Task

In the Claude Code prompt, enter:

```
Create a simple Python hello world project with a README and a test file, then run the test.
```

**While Claude Code works, observe and note:**

1. **Permission prompts** — Does it ask before creating files? Before running shell commands? Record exactly what it asks and what you approve.
2. **Sequence of operations** — Watch the order: directory read → file write → file write → shell command → result processing. This is the agentic loop.
3. **Child processes** — In the process tree monitor, look for: `claude` → `sh`/`bash` → `python`/`pytest` child chains.
4. **Git operations** — Does Claude Code run `git init`, `git add`, `git commit`? This validates the git-related IOCs.

### Post-Task Capture

After Claude Code completes the task:

```bash
# All files in workspace with timestamps
find ~/claude-lab-workspace -type f -ls > "$LAB_DIR/phase3-agentic/workspace-files.txt"

# File contents (small project, safe to capture entirely)
for f in $(find ~/claude-lab-workspace -type f -not -path '*/__pycache__/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt"
  echo "" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt"
done

# Files changed across all of home since Phase 2
find ~ -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" \
  -not -path '*/claude-lab/*' \
  2>/dev/null > "$LAB_DIR/phase3-agentic/new-files-during-agentic.txt"

# Claude state directory (session artifacts?)
ls -laR ~/.claude > "$LAB_DIR/phase3-agentic/claude-dir-post-agentic.txt" 2>&1
diff "$LAB_DIR/phase2-launch/claude-dir-at-launch.txt" \
  "$LAB_DIR/phase3-agentic/claude-dir-post-agentic.txt" \
  > "$LAB_DIR/phase3-agentic/claude-dir-diff.txt" 2>&1
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID $INOTIFY_PID 2>/dev/null
sudo kill $TCPDUMP_PID $STRACE_PID 2>/dev/null
```

### Phase 3 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3-agentic/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3-agentic/phase3-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3-agentic/"* > "$LAB_DIR/phase3-agentic/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Session End — What Persists After Exit

**Purpose:** Determine what survives after the Claude Code session ends. Persistent state has forensic value and is a key File/Artifact layer signal.

### Exit Claude Code

Type `/exit` or `Ctrl+C` in the Claude Code prompt. Exit the `script` session with `exit`.

### Wait and Capture

Allow 10 seconds for cleanup, then:

```bash
# Process check: is anything still running?
ps auxww | grep -E 'claude|anthropic' | grep -v grep > "$LAB_DIR/phase4-teardown/remaining-processes.txt"
echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt")" \
  >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"

# Orphan child processes?
pstree -p > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null || \
  ps auxf > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt"

# Lingering network connections
ss -tnp > "$LAB_DIR/phase4-teardown/connections-post-exit.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/phase4-teardown/connections-post-exit.txt"
diff "$LAB_DIR/baseline/active-connections.txt" \
  "$LAB_DIR/phase4-teardown/connections-post-exit.txt" \
  > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1

# Listening ports
ss -tlnp > "$LAB_DIR/phase4-teardown/listening-ports-post.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/phase4-teardown/listening-ports-post.txt"

# Persistent files and state
ls -laR ~/.claude > "$LAB_DIR/phase4-teardown/claude-dir-final.txt" 2>&1

# Full diff: what files exist now that didn't at baseline?
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt"

# Session/history artifacts in claude dir
find ~/.claude -type f -exec ls -la {} \; 2>/dev/null > "$LAB_DIR/phase4-teardown/claude-artifacts-detail.txt"
find ~/.claude -type f -exec file {} \; 2>/dev/null >> "$LAB_DIR/phase4-teardown/claude-artifacts-detail.txt"

# Shell profile modifications
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase4-teardown/shellprofile-diff-$base.txt" 2>&1
  fi
done

# Persistence mechanisms
crontab -l > "$LAB_DIR/phase4-teardown/crontab-final.txt" 2>&1
diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase4-teardown/crontab-final.txt" \
  > "$LAB_DIR/phase4-teardown/crontab-diff.txt" 2>&1

# Linux: new systemd user services?
systemctl --user list-units --type=service > "$LAB_DIR/phase4-teardown/user-services-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/user-services.txt" "$LAB_DIR/phase4-teardown/user-services-final.txt" \
  > "$LAB_DIR/phase4-teardown/services-diff.txt" 2>&1

# macOS: new LaunchAgents?
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1
```

### Phase 4 Timestamp and Hashes

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase4-teardown/phase4-end-time.txt"
shasum -a 256 "$LAB_DIR/phase4-teardown/"* > "$LAB_DIR/phase4-teardown/EVIDENCE-HASHES.txt" 2>/dev/null
```

### Final Evidence Integrity Hash

```bash
find "$LAB_DIR" -name 'EVIDENCE-HASHES.txt' -exec cat {} \; > "$LAB_DIR/MASTER-HASHES.txt"
shasum -a 256 "$LAB_DIR/MASTER-HASHES.txt" >> "$LAB_DIR/MASTER-HASHES.txt"
```

---

## Phase 5: Evidence Analysis and Template Completion

### 5.1 Signal Observation Matrix

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.1:

| Layer | IOC (from Section 4.1) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | CLI binary invocation from terminal parent | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Child process chain: claude → shell → git/node/python | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Long-lived interactive sessions with command bursts | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `~/.claude/` config/state directories | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Session history/cache artifacts with recent timestamps | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Prompt/context helper files near repo roots | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | TLS/SNI to `api.anthropic.com`, `claude.ai` | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Request burst cadence matching prompt→response→action | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | API key env vars (`ANTHROPIC_API_KEY`) tied to session | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Rapid multi-file read/write loops across repo | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Shell command orchestration from AI session context | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Git commit/patch generation after model interaction | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

### 5.2 Correlation Rule Evaluation (INIT-43 / Appendix A)

| Rule | Requirement | Result |
|------|--------------|--------|
| **C1** High-confidence | Process entrypoint + lineage, at least one fresh artifact, network timing or behavioral continuity | `[ ] Met` `[ ] Not met` |
| **C2** Medium-confidence | Any two layers align; missing process certainty or artifact recency | `[ ] Met` `[ ] Not met` |
| **C3** Low-confidence | Single-layer only or conflicting signals | `[ ] Met` `[ ] Not met` |
| **C4** Ambiguity override | Layers conflict; downgrade to warn/approval only | `[ ] Met` `[ ] Not met` |

### 5.3 Confidence Score Calculation

Using Appendix B formula with Claude Code signal weights (INIT-43):

```
Layer Weights (three-layer from INIT-43):
  Process:  0.45
  File:     0.30
  Network:  0.25

Five-layer defaults (Appendix B):
  Process:  0.30
  File:     0.20
  Network:  0.15
  Identity: 0.15
  Behavior: 0.20
```

```
base_score = Σ (layer_weight × layer_signal_strength)

Applicable penalties:
  [ ] Missing parent-child process chain:          −0.15
  [ ] Wrapper/renamed binary without resolution:   −0.15
  [ ] Stale artifact only (no recent modification): −0.10
  [ ] Non-default artifact paths:                  −0.10
  [ ] Ambiguous proxy/gateway route:               −0.10
  [ ] Unresolved process-to-network linkage:       −0.10
  [ ] Containerized/remote execution:              −0.10
  [ ] Weak/missing identity correlation:           −0.10

penalties = Σ (applicable penalties)
final_confidence = max(0, base_score - penalties)

Classification:
  ≥ 0.75  → High    → Enables Approval Required / Block
  0.45–0.74 → Medium → Enables Warn + step-up
  < 0.45  → Low     → Detect-only
```

**Calculated score:** `___`  
**Classification:** `___`  
**Does this score seem right given what you observed?** `___`

### 5.4 Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-001
Date:                [execution date]
Tool:                Claude Code [version from npm list -g]
Scenario ID:         CC-POS-01 (Standard CLI install + agentic task)
Environment:         [OS version, endpoint posture, network topology]
Scenario Type:       Positive

Signal Observations:
  Process:           [observed / not observed — cite evidence files]
  File/Artifact:     [observed / not observed — cite evidence files]
  Network:           [observed / not observed — cite evidence files]
  Identity:          [observed / not observed — cite evidence files]
  Behavior:          [observed / not observed — cite evidence files]

Confidence Result:   [score + rationale]
Policy Decision:     [detect/warn/approval/block + rule_id from Section 6.3]
Evidence Links:      [list of evidence files with hashes from MASTER-HASHES.txt]
Pass/Fail:           [pass | conditional pass | fail]
Residual Risk:       [coverage gaps identified during the run]
```

### 5.5 Findings and Playbook Feedback

Document any observations that should feed back into the playbook:

| Finding | Affected Section | Recommended Change |
|---|---|---|
| | | |
| | | |
| | | |

---

## INIT-43 Validation Plan Coverage

From INIT-43 Section 7:

- **Positive checks:** (1) Canonical Claude CLI session with process/file/network alignment → CC-POS-01 (this run). (2) Multi-command/workflow with artifact and network corroboration → CC-POS-02 (git-heavy task). (3) Repeated session consistency → rerun or CC-POS-03 when defined.
- **Adversarial checks:** Wrapper/renamed binary, proxy-routed API → CC-EVA-01 (see LAB-RUN-EVASION-001); same four outputs required.
- **Required outputs (must appear in RESULTS):**
  1. **Per-layer signal capture report** → Section 1 "Signal Observation Matrix" in LAB-RUN-001-RESULTS.md
  2. **Confidence calculation trace** → Section 2 "Confidence Score Calculation" in LAB-RUN-001-RESULTS.md
  3. **Correlation rule evaluation** → Section 5.2 above; summarize in RESULTS
  4. **Residual ambiguity notes** → "Residual Risk" in completed evidence template (Section 5.4) and in RESULTS

---

## Evidence Inventory Checklist

When complete, `$LAB_DIR` should contain:

```
LAB-RUN-001/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── claude-dir-check.txt
│   ├── claude-artifact-scan.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── env-vars.txt
│   ├── anthropic-env.txt
│   ├── npm-globals.txt
│   ├── which-claude.txt
│   ├── user-services.txt
│   ├── crontab.txt
│   ├── launch-agents.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── npm-install-output.txt        ← full install log
│   ├── claude-version.json           ← explicit version + dependency tree (JSON)
│   ├── install-traffic.pcap          ← network capture
│   ├── dns-queries.txt
│   ├── ps-stream.txt
│   ├── npm-globals-post.txt
│   ├── npm-globals-diff.txt
│   ├── which-claude.txt
│   ├── binary-metadata.txt           ← hash, path, symlinks
│   ├── new-files.txt
│   ├── claude-dir-post.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-post.txt
│   └── crontab-diff.txt
├── phase2-launch/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── terminal-session.log          ← full TTY recording
│   ├── launch-traffic.pcap
│   ├── connections-stream.txt
│   ├── pstree-stream.txt
│   ├── claude-process-tree.txt
│   ├── auth-processes.txt            ← auth flow capture
│   ├── listening-ports-during-auth.txt
│   ├── outbound-at-launch.txt
│   ├── claude-tree-idle.txt
│   ├── new-files-at-launch.txt
│   ├── claude-dir-at-launch.txt
│   ├── claude-config-contents.txt    ← permission model
│   └── strace-launch.txt            ← syscall trace (Linux)
├── phase3-agentic/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── terminal-session.log          ← agentic session recording
│   ├── agentic-traffic.pcap
│   ├── pstree-stream.txt             ← 1-second resolution
│   ├── file-events.txt               ← inotify/fswatch
│   ├── connections-stream.txt
│   ├── strace-agentic.txt            ← syscall trace (Linux)
│   ├── workspace-files.txt
│   ├── workspace-contents.txt
│   ├── new-files-during-agentic.txt
│   ├── claude-dir-post-agentic.txt
│   └── claude-dir-diff.txt
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── remaining-processes.txt
│   ├── pstree-post-exit.txt
│   ├── connections-post-exit.txt
│   ├── connections-diff.txt
│   ├── listening-ports-post.txt
│   ├── claude-dir-final.txt
│   ├── claude-artifacts-detail.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── user-services-final.txt
│   ├── services-diff.txt
│   ├── launch-agents-final.txt
│   └── launch-agents-diff.txt
└── [Phase 5 analysis filled in manually or in a separate doc]
```

---

## Post-Run: Next Steps

1. **Complete the Section 5 analysis** — fill in every cell of the observation matrix and calculate the confidence score.
2. **Update the Playbook Lab Run Log** (Section 12.4) with results.
3. **File playbook feedback** for any IOCs that were predicted incorrectly or missing.
4. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
5. **Plan next run** — CC-POS-02 (multi-file refactor + git) or CC-EVA-01 (renamed binary evasion).
