# Lab Run Protocol: Cursor IDE Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-004  
**Tool:** Cursor (Electron-based IDE, VS Code fork)  
**Class:** A (SaaS Copilot / Assistive IDE) → escalates to C (Autonomous Executor) when terminal agent workflows execute  
**Playbook Reference:** Section 4.2 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Standard IDE session + AI-assisted editing + agentic task execution  
**Scenario ID:** CUR-POS-01  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | macOS (native, Apple Silicon or Intel) |
| **Shell** | zsh or bash |
| **Root/sudo** | Required for `tcpdump`; optional — `lsof` and `ps` work without elevation |
| **Disk** | Sufficient space for evidence artifacts (~500 MB headroom) |
| **Network** | Outbound internet access (Cursor cloud AI endpoints) |
| **Cursor** | Already installed at `/Applications/Cursor.app` |

### Tool Availability Check

Run before starting. All must be present:

```bash
which lsof           # port/connection inspection
which pstree         # process tree viewer (brew install pstree)
which script         # terminal session recorder
file /Applications/Cursor.app/Contents/MacOS/Cursor  # binary check
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/cursor-lab/LAB-RUN-004
mkdir -p "$LAB_DIR"/{baseline,phase1-footprint,phase2-launch,phase3a-classA,phase3b-classC,phase4-teardown}
```

---

## Pre-Run: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer. Since Cursor is already installed and running (we are executing from within it), the baseline captures the current state including the active Cursor session.

> **Key difference from other lab runs:** We cannot capture a "pre-install" baseline because the tool is already installed and actively running. The baseline here captures the existing state of the running system, which includes Cursor's own processes and artifacts. This is noted in the analysis.

### File System Baseline

```bash
# Home directory tree (depth-limited)
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

# Cursor-specific artifact check — what already exists
ls -la ~/.cursor 2>&1 > "$LAB_DIR/baseline/cursor-global-dir.txt"
ls -laR ~/.cursor/ 2>&1 > "$LAB_DIR/baseline/cursor-global-dir-recursive.txt"

# Workspace-level .cursor directory (this project)
find . -name '.cursor' -type d 2>/dev/null > "$LAB_DIR/baseline/workspace-cursor-dirs.txt"
ls -laR .cursor/ 2>&1 >> "$LAB_DIR/baseline/workspace-cursor-dirs.txt"

# /tmp state
ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"

# Shell profile snapshots
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename $f).bak"
done
```

### Process Baseline

```bash
# Full process listing
ps auxww > "$LAB_DIR/baseline/ps-full.txt"

# Process tree
pstree > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || ps auxf > "$LAB_DIR/baseline/ps-tree.txt"

# Cursor-specific processes already running
ps auxww | grep -i '[Cc]ursor' > "$LAB_DIR/baseline/cursor-processes.txt" 2>&1
echo "Matching processes: $(wc -l < "$LAB_DIR/baseline/cursor-processes.txt")" \
  >> "$LAB_DIR/baseline/cursor-processes.txt"

# Electron helper processes (Cursor is Electron-based)
ps auxww | grep -i '[Cc]ursor' | grep -i 'Helper' > "$LAB_DIR/baseline/cursor-helper-processes.txt" 2>&1
```

### Network Baseline

```bash
# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"

# Active outbound connections
lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"

# Cursor-specific network activity
lsof -i -nP | grep -i '[Cc]ursor' > "$LAB_DIR/baseline/cursor-network.txt" 2>&1
```

### Environment Baseline

```bash
# Full environment dump
env | sort > "$LAB_DIR/baseline/env-vars.txt"

# Cursor-specific env check
env | grep -i cursor > "$LAB_DIR/baseline/cursor-env.txt" 2>/dev/null
echo "Exit code: $? (1 = no CURSOR vars found)" >> "$LAB_DIR/baseline/cursor-env.txt"
```

### Persistence Mechanism Baseline

```bash
# macOS: LaunchAgents
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null

# Cursor-specific LaunchAgents/Daemons
find ~/Library/LaunchAgents /Library/LaunchDaemons -name '*cursor*' -o -name '*Cursor*' \
  2>/dev/null > "$LAB_DIR/baseline/cursor-plist-check.txt"
echo "Exit code: $? (1 = none found)" >> "$LAB_DIR/baseline/cursor-plist-check.txt"

# Crontab
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1

# Login items
osascript -e 'tell application "System Events" to get the name of every login item' \
  > "$LAB_DIR/baseline/login-items.txt" 2>&1
```

### App Bundle Metadata

```bash
# Capture Cursor app bundle metadata (this is install-footprint data)
ls -la /Applications/Cursor.app/Contents/MacOS/ > "$LAB_DIR/baseline/cursor-binary-listing.txt" 2>&1
file /Applications/Cursor.app/Contents/MacOS/Cursor > "$LAB_DIR/baseline/cursor-binary-type.txt" 2>&1
codesign -dvv /Applications/Cursor.app > "$LAB_DIR/baseline/cursor-codesign.txt" 2>&1
shasum -a 256 /Applications/Cursor.app/Contents/MacOS/Cursor > "$LAB_DIR/baseline/cursor-binary-hash.txt" 2>&1

# App version from Info.plist
defaults read /Applications/Cursor.app/Contents/Info.plist CFBundleShortVersionString \
  > "$LAB_DIR/baseline/cursor-version.txt" 2>&1
defaults read /Applications/Cursor.app/Contents/Info.plist CFBundleVersion \
  >> "$LAB_DIR/baseline/cursor-version.txt" 2>&1

# Electron version
defaults read /Applications/Cursor.app/Contents/Info.plist ElectronVersion \
  >> "$LAB_DIR/baseline/cursor-version.txt" 2>&1
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

## Phase 1: Existing Install Footprint — What Is Already on Disk

**Purpose:** Capture the full installation footprint of the already-installed Cursor app — binary, app bundle, global config directories, extensions, settings, and any account/identity state. Since Cursor is pre-installed, this phase replaces the "installation" phase used in other lab runs.

> **Key difference from Class C/B tools:** Cursor is a desktop app distributed as a `.dmg`, not via `npm` or `brew`. The install footprint is an `.app` bundle in `/Applications/`, plus user-level config in `~/.cursor/`. There is no package manager metadata, no postinstall script to capture — the app was installed via drag-to-Applications.

### App Bundle Analysis

```bash
# Full app bundle structure (top-level, too deep to capture entirely)
find /Applications/Cursor.app -maxdepth 3 -type f 2>/dev/null | head -100 \
  > "$LAB_DIR/phase1-footprint/app-bundle-structure.txt"

# Count total files in bundle
echo "Total files in app bundle:" >> "$LAB_DIR/phase1-footprint/app-bundle-structure.txt"
find /Applications/Cursor.app -type f 2>/dev/null | wc -l \
  >> "$LAB_DIR/phase1-footprint/app-bundle-structure.txt"

# Bundle size
du -sh /Applications/Cursor.app > "$LAB_DIR/phase1-footprint/app-bundle-size.txt" 2>&1

# Frameworks included (Electron bundles Chromium)
ls -la /Applications/Cursor.app/Contents/Frameworks/ \
  > "$LAB_DIR/phase1-footprint/frameworks.txt" 2>&1
```

### Global Config Directory (~/.cursor/)

```bash
# Full directory listing
ls -laR ~/.cursor/ > "$LAB_DIR/phase1-footprint/cursor-global-full.txt" 2>&1

# Directory structure only
find ~/.cursor -type d 2>/dev/null > "$LAB_DIR/phase1-footprint/cursor-global-dirs.txt"

# File count and total size
echo "File count:" > "$LAB_DIR/phase1-footprint/cursor-global-stats.txt"
find ~/.cursor -type f 2>/dev/null | wc -l >> "$LAB_DIR/phase1-footprint/cursor-global-stats.txt"
echo "Total size:" >> "$LAB_DIR/phase1-footprint/cursor-global-stats.txt"
du -sh ~/.cursor/ >> "$LAB_DIR/phase1-footprint/cursor-global-stats.txt" 2>&1
```

### Extensions Inventory

```bash
# List installed extensions
ls -la ~/.cursor/extensions/ > "$LAB_DIR/phase1-footprint/extensions-listing.txt" 2>&1

# Extension details (names, versions)
find ~/.cursor/extensions -maxdepth 1 -type d -name '*.*' 2>/dev/null \
  | sort > "$LAB_DIR/phase1-footprint/extensions-inventory.txt"
```

### Settings and Configuration

```bash
# User settings
cat ~/.cursor/User/settings.json > "$LAB_DIR/phase1-footprint/user-settings.json" 2>/dev/null
cat ~/.cursor/User/keybindings.json > "$LAB_DIR/phase1-footprint/user-keybindings.json" 2>/dev/null

# State databases (presence check, not content — they may be SQLite)
find ~/.cursor -name '*.db' -o -name '*.sqlite' -o -name '*.vscdb' 2>/dev/null \
  > "$LAB_DIR/phase1-footprint/state-databases.txt"

# AI feature state / settings
find ~/.cursor -name '*ai*' -o -name '*copilot*' -o -name '*chat*' -o -name '*agent*' \
  2>/dev/null > "$LAB_DIR/phase1-footprint/ai-feature-artifacts.txt"
```

### Account / Identity State

```bash
# Look for account/auth state files
find ~/.cursor -name '*auth*' -o -name '*account*' -o -name '*session*' -o -name '*token*' \
  -o -name '*credential*' -o -name '*login*' 2>/dev/null \
  > "$LAB_DIR/phase1-footprint/identity-artifacts.txt"

# Cursor-specific storage (may contain account info)
find ~/.cursor -name 'storage.json' -o -name 'state.vscdb' 2>/dev/null \
  > "$LAB_DIR/phase1-footprint/storage-files.txt"

# Check for account info in settings-like files
find ~/.cursor -name '*.json' -maxdepth 3 -exec grep -l -i 'email\|account\|auth\|token' {} \; \
  2>/dev/null > "$LAB_DIR/phase1-footprint/json-with-identity.txt"
```

### Workspace .cursor/ Directory

```bash
# Current workspace's .cursor/ directory (project-local Cursor config)
ls -laR .cursor/ > "$LAB_DIR/phase1-footprint/workspace-cursor-dir.txt" 2>&1

# Rules files (Cursor rules for AI behavior)
find .cursor -name '*.mdc' -o -name '*.md' -o -name 'rules' 2>/dev/null \
  > "$LAB_DIR/phase1-footprint/cursor-rules-files.txt"

# Skills files
find .cursor -name 'SKILL.md' 2>/dev/null \
  > "$LAB_DIR/phase1-footprint/cursor-skills-files.txt"
```

### Phase 1 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase1-footprint/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-footprint/phase1-end-time.txt"
shasum -a 256 "$LAB_DIR/phase1-footprint/"* > "$LAB_DIR/phase1-footprint/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 2: Launch & Idle State — Process Tree, Network Activity, Initial State

**Purpose:** Capture Cursor's runtime state — the multi-process Electron architecture, network connections to cloud AI endpoints, and initial process tree. Since Cursor is already running (we are inside it), this captures the *current* runtime state rather than a fresh launch.

> **Key difference from Class C/B tools:** Cursor is a multi-process Electron app with a complex process tree: main process, renderer processes (one per tab/window), extension host, GPU process, utility processes, and embedded terminal processes. This is fundamentally different from a single CLI binary (Claude Code) or daemon (Ollama).

### Process Tree Capture

```bash
# Full process tree for Cursor
ps auxww | grep -i '[Cc]ursor' > "$LAB_DIR/phase2-launch/cursor-all-processes.txt" 2>&1

# Process count
echo "Total Cursor processes:" >> "$LAB_DIR/phase2-launch/cursor-all-processes.txt"
ps auxww | grep -i '[Cc]ursor' | grep -v grep | wc -l >> "$LAB_DIR/phase2-launch/cursor-all-processes.txt"

# Process tree from the main Cursor PID
CURSOR_MAIN_PID=$(pgrep -f '/Applications/Cursor.app/Contents/MacOS/Cursor$' | head -1)
echo "Main Cursor PID: $CURSOR_MAIN_PID" > "$LAB_DIR/phase2-launch/cursor-main-pid.txt"
if [ -n "$CURSOR_MAIN_PID" ]; then
  pstree -p "$CURSOR_MAIN_PID" > "$LAB_DIR/phase2-launch/cursor-process-tree.txt" 2>/dev/null
fi

# Categorize Cursor helper processes
ps auxww | grep -i '[Cc]ursor' | grep -i 'Helper' > "$LAB_DIR/phase2-launch/cursor-helpers.txt" 2>&1
ps auxww | grep -i '[Cc]ursor' | grep -i 'GPU' >> "$LAB_DIR/phase2-launch/cursor-helpers.txt" 2>&1
ps auxww | grep -i '[Cc]ursor' | grep -i 'Utility' >> "$LAB_DIR/phase2-launch/cursor-helpers.txt" 2>&1
ps auxww | grep -i '[Cc]ursor' | grep -i 'Renderer' >> "$LAB_DIR/phase2-launch/cursor-helpers.txt" 2>&1

# Resource usage snapshot
ps -p $(pgrep -f '[Cc]ursor' | tr '\n' ',') -o pid,ppid,rss,vsz,%mem,%cpu,etime,comm \
  2>/dev/null > "$LAB_DIR/phase2-launch/cursor-resource-usage.txt"
```

### Network Activity Capture

```bash
# All network connections from Cursor processes
lsof -i -nP | grep -i '[Cc]ursor' > "$LAB_DIR/phase2-launch/cursor-network-all.txt" 2>&1

# Listening ports
lsof -i -nP | grep -i '[Cc]ursor' | grep LISTEN > "$LAB_DIR/phase2-launch/cursor-listening-ports.txt" 2>&1

# Established connections (outbound to AI endpoints)
lsof -i -nP | grep -i '[Cc]ursor' | grep ESTABLISHED > "$LAB_DIR/phase2-launch/cursor-established.txt" 2>&1

# DNS-resolvable destinations (extract unique IPs and attempt reverse lookup)
lsof -i -nP | grep -i '[Cc]ursor' | grep ESTABLISHED | awk '{print $9}' | \
  cut -d'>' -f2 | cut -d':' -f1 | sort -u > "$LAB_DIR/phase2-launch/cursor-dest-ips.txt" 2>&1

# Attempt reverse DNS on destination IPs
while read ip; do
  echo "=== $ip ===" >> "$LAB_DIR/phase2-launch/cursor-dest-dns.txt"
  host "$ip" >> "$LAB_DIR/phase2-launch/cursor-dest-dns.txt" 2>&1
done < "$LAB_DIR/phase2-launch/cursor-dest-ips.txt"
```

### Extension Host State

```bash
# Extension host process details
ps auxww | grep -i 'extensionHost' > "$LAB_DIR/phase2-launch/extension-host.txt" 2>&1

# Shared process (Cursor may run extension host in shared mode)
ps auxww | grep -i 'sharedProcess' >> "$LAB_DIR/phase2-launch/extension-host.txt" 2>&1
```

### Connection Stream (background monitor for subsequent phases)

```bash
# Start connection snapshot monitor (runs through Phases 3A and 3B)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/connections-stream.txt"
  lsof -i -nP | grep -i '[Cc]ursor' >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!
echo "Connection monitor PID: $CONN_PID" > "$LAB_DIR/phase2-launch/monitor-pids.txt"

# Start process snapshot monitor
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
  ps auxww | grep -i '[Cc]ursor' >> "$LAB_DIR/phase2-launch/pstree-stream.txt" 2>/dev/null
  sleep 2
done &
PS_PID=$!
echo "Process monitor PID: $PS_PID" >> "$LAB_DIR/phase2-launch/monitor-pids.txt"
```

### Phase 2 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-launch/phase2-end-time.txt"
shasum -a 256 "$LAB_DIR/phase2-launch/"* > "$LAB_DIR/phase2-launch/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3A: Class A Behavior — AI-Assisted Editing (Assistive Mode)

**Purpose:** Validate Class A (SaaS Copilot) IOCs. Exercise Cursor's AI chat and autocomplete features for simple editing tasks — code suggestions, inline completions, chat-based questions. This is the baseline assistive behavior before any agentic escalation.

> **Key difference from other lab runs:** This phase has no equivalent in the Claude Code or Ollama protocols. It captures the *baseline* Class A behavior — the IDE acting as an assistant rather than an autonomous executor. The behavioral signals here are: prompt-response editing cycles, AI-generated suggestions, and chat interaction — but NO shell execution, NO multi-file autonomous writes, NO git operations.

### Pre-Phase 3A Snapshot

```bash
# Process state before AI interaction
ps auxww | grep -i '[Cc]ursor' > "$LAB_DIR/phase3a-classA/processes-before.txt" 2>&1

# Network state before AI interaction
lsof -i -nP | grep -i '[Cc]ursor' > "$LAB_DIR/phase3a-classA/network-before.txt" 2>&1

# File state before AI interaction
ls -laR ~/.cursor/ > "$LAB_DIR/phase3a-classA/cursor-dir-before.txt" 2>&1
```

### Exercise Class A Features

In the Cursor IDE, perform these actions (manually, through the AI chat/edit features):

1. **Open AI chat** (Cmd+L or Cmd+I) and ask a simple question: "What is a Python decorator?"
2. **Use inline completion** — open or create a `.py` file and let Cursor suggest completions
3. **Use Cmd+K** — select some code and ask Cursor to modify it

> **Note for automated execution:** If executing from within Cursor's own terminal agent, these Class A interactions may be limited. The key evidence is the network traffic and state file changes that occur during any AI feature usage — which the current agent session already generates.

### Post-Class A Capture

```bash
# Process state after AI interaction
ps auxww | grep -i '[Cc]ursor' > "$LAB_DIR/phase3a-classA/processes-after.txt" 2>&1

# Network state after AI interaction
lsof -i -nP | grep -i '[Cc]ursor' > "$LAB_DIR/phase3a-classA/network-after.txt" 2>&1

# File changes since Phase 2
find ~ -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" \
  -not -path '*/cursor-lab/*' \
  -not -path '*/.cache/*' \
  -not -path '*/node_modules/*' \
  2>/dev/null > "$LAB_DIR/phase3a-classA/new-files-classA.txt"

# Cursor state directory changes
ls -laR ~/.cursor/ > "$LAB_DIR/phase3a-classA/cursor-dir-after.txt" 2>&1
diff "$LAB_DIR/phase3a-classA/cursor-dir-before.txt" \
  "$LAB_DIR/phase3a-classA/cursor-dir-after.txt" \
  > "$LAB_DIR/phase3a-classA/cursor-dir-diff.txt" 2>&1

# AI-specific logs or state changes
find ~/.cursor -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" -type f \
  2>/dev/null > "$LAB_DIR/phase3a-classA/cursor-changed-files.txt"
```

### Phase 3A Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3a-classA/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3a-classA/phase3a-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3a-classA/"* > "$LAB_DIR/phase3a-classA/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3B: Class C Behavior — Agentic Task Execution (Autonomous Mode)

**Purpose:** Validate Class C (Autonomous Executor) IOCs by exercising Cursor's terminal agent features. Trigger the class escalation from A to C by requesting an agentic task that requires shell execution, multi-file writes, and git operations. This is the critical phase for validating the class escalation model.

> **Key difference from Claude Code Phase 3:** Cursor's agentic mode operates through an embedded terminal within the IDE, not a standalone CLI binary. The process chain is: `Cursor.app` → `extension host` → `terminal` → `shell` → child processes. The agent uses tool calls (shell execution, file writes) that are mediated through the IDE's extension system. The behavioral signals should match Class C patterns (multi-file writes, shell orchestration) but with an IDE-native process lineage.

### Prepare Clean Working Directory

```bash
mkdir -p ~/cursor-lab-workspace && cd ~/cursor-lab-workspace
```

### Start Enhanced Monitors

```bash
# Higher-frequency process monitoring for agentic bursts (every 1 second)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3b-classC/pstree-stream.txt"
  ps auxww | grep -i '[Cc]ursor' >> "$LAB_DIR/phase3b-classC/pstree-stream.txt" 2>/dev/null
  sleep 1
done &
PS3B_PID=$!

# File change watcher on workspace (macOS: use fswatch if available)
if which fswatch >/dev/null 2>&1; then
  fswatch ~/cursor-lab-workspace > "$LAB_DIR/phase3b-classC/file-events.txt" 2>/dev/null &
  FSWATCH_PID=$!
fi

# Connection monitor at 1-second resolution
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3b-classC/connections-stream.txt"
  lsof -i -nP | grep -i '[Cc]ursor' >> "$LAB_DIR/phase3b-classC/connections-stream.txt" 2>/dev/null
  sleep 1
done &
CONN3B_PID=$!
```

### Issue the Agentic Task

Use Cursor's agent mode (Cmd+I with agent, or the composer agent) to execute:

```
Create a simple Python hello world project in ~/cursor-lab-workspace with a README.md and a test file using pytest, then run the tests.
```

**While the agent works, observe and note:**

1. **Permission prompts** — Does Cursor ask before creating files? Before running shell commands? Record what it asks and approves.
2. **Terminal activity** — Watch for embedded terminal sessions spawning shell commands.
3. **File creation sequence** — Multi-file writes in rapid succession (the agentic loop signature).
4. **Process tree changes** — New child processes under Cursor's process tree.
5. **Network bursts** — Increased traffic to Cursor cloud endpoints during the agentic loop.

### Post-Task Capture

```bash
# All files in workspace with timestamps
find ~/cursor-lab-workspace -type f -ls > "$LAB_DIR/phase3b-classC/workspace-files.txt"

# File contents (small project, safe to capture)
for f in $(find ~/cursor-lab-workspace -type f -not -path '*/__pycache__/*' -not -path '*/.git/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3b-classC/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3b-classC/workspace-contents.txt" 2>/dev/null
  echo "" >> "$LAB_DIR/phase3b-classC/workspace-contents.txt"
done

# Git state check
ls -la ~/cursor-lab-workspace/.git > "$LAB_DIR/phase3b-classC/git-check.txt" 2>&1
cd ~/cursor-lab-workspace && git log --oneline --all > "$LAB_DIR/phase3b-classC/git-log.txt" 2>&1
git log --format=full > "$LAB_DIR/phase3b-classC/git-log-full.txt" 2>&1
cd -

# Files changed across home since Phase 3A
find ~ -newer "$LAB_DIR/phase3a-classA/TIMESTAMP_MARKER" \
  -not -path '*/cursor-lab/*' \
  -not -path '*/.cache/*' \
  -not -path '*/node_modules/*' \
  2>/dev/null > "$LAB_DIR/phase3b-classC/new-files-classC.txt"

# Cursor state directory changes since Phase 3A
ls -laR ~/.cursor/ > "$LAB_DIR/phase3b-classC/cursor-dir-post-agentic.txt" 2>&1
diff "$LAB_DIR/phase3a-classA/cursor-dir-after.txt" \
  "$LAB_DIR/phase3b-classC/cursor-dir-post-agentic.txt" \
  > "$LAB_DIR/phase3b-classC/cursor-dir-diff.txt" 2>&1

# Workspace .cursor/ directory changes
ls -laR .cursor/ > "$LAB_DIR/phase3b-classC/workspace-cursor-post.txt" 2>&1

# Agent transcript / session state (if Cursor stores agent session history)
find ~/.cursor -name '*agent*' -o -name '*composer*' -o -name '*transcript*' \
  2>/dev/null > "$LAB_DIR/phase3b-classC/agent-session-artifacts.txt"
find ~/.cursor -newer "$LAB_DIR/phase3a-classA/TIMESTAMP_MARKER" -type f \
  2>/dev/null > "$LAB_DIR/phase3b-classC/cursor-changed-files.txt"
```

### Stop Enhanced Monitors

```bash
kill $PS3B_PID $CONN3B_PID 2>/dev/null
kill $FSWATCH_PID 2>/dev/null
```

### Phase 3B Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3b-classC/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3b-classC/phase3b-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3b-classC/"* > "$LAB_DIR/phase3b-classC/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Teardown — What Persists After Session

**Purpose:** Determine what survives after the Cursor session. Unlike CLI tools that leave only passive state, and daemons that maintain active persistence, Cursor is an interactive desktop app — its persistence profile is expected to include settings, extensions, session state, and possibly account credentials, but no daemon or background service.

> **Note:** We will NOT quit Cursor for this phase (since we're running inside it). Instead, we capture the full state and note what would persist after quit based on the artifact inventory.

### Capture Persistent State

```bash
# Stop background monitors from Phase 2
kill $CONN_PID $PS_PID 2>/dev/null

# Process state
ps auxww | grep -i '[Cc]ursor' > "$LAB_DIR/phase4-teardown/cursor-processes-final.txt" 2>&1

# Network state
lsof -i -nP | grep -i '[Cc]ursor' > "$LAB_DIR/phase4-teardown/cursor-network-final.txt" 2>&1

# Full cursor directory — final state
ls -laR ~/.cursor/ > "$LAB_DIR/phase4-teardown/cursor-dir-final.txt" 2>&1

# Diff against baseline
diff "$LAB_DIR/baseline/cursor-global-dir-recursive.txt" \
  "$LAB_DIR/phase4-teardown/cursor-dir-final.txt" \
  > "$LAB_DIR/phase4-teardown/cursor-dir-diff-from-baseline.txt" 2>&1

# Full diff: what files exist now that didn't at baseline?
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt" 2>&1

# Cursor artifact detail
find ~/.cursor -type f -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -exec ls -la {} \; 2>/dev/null > "$LAB_DIR/phase4-teardown/cursor-changed-artifacts.txt"

# Shell profile modifications
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase4-teardown/shellprofile-diff-$base.txt" 2>&1
  fi
done

# Persistence mechanisms — diff against baseline
crontab -l > "$LAB_DIR/phase4-teardown/crontab-final.txt" 2>&1
diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase4-teardown/crontab-final.txt" \
  > "$LAB_DIR/phase4-teardown/crontab-diff.txt" 2>&1

ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1

# Disk usage of Cursor directories
du -sh ~/.cursor/ > "$LAB_DIR/phase4-teardown/cursor-disk-usage.txt" 2>&1
du -sh /Applications/Cursor.app > "$LAB_DIR/phase4-teardown/cursor-app-disk-usage.txt" 2>&1
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

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.2:

| Layer | IOC (from Section 4.2) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | Signed Cursor app process from standard install paths | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Child process lineage: Cursor → embedded terminal → shell/git/node | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Sustained session with child process and file-write bursts | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `~/.cursor/`, workspace `.cursor/` settings and extension state files | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | AI feature cache/session files with recent timestamps | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Burst edits across repo files with consistent timing | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | TLS/SNI to Cursor cloud/model infrastructure endpoints | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Request bursts aligned with prompt-response editing cycles | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | Cursor account state (corporate vs personal) on managed endpoint | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | High-frequency multi-file edit loops after prompt interaction cadence | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Context-heavy reads + concentrated writes (agentic edit shape) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Shell invocations proximate to AI edit sequences | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

### 5.2 Class Escalation Analysis

Document the class escalation behavior unique to Cursor:

| Question | Finding |
|---|---|
| What process/behavioral signals distinguish Class A from Class C mode? | |
| Does the process tree change when the agent feature is activated? | |
| Are there distinct network patterns between chat-only and agentic usage? | |
| What file artifacts are created during agentic vs assistive sessions? | |
| Can Class C behavior be detected from process telemetry alone? | |
| Is there a single signal that reliably indicates class escalation? | |

### 5.3 Confidence Score Calculation

Using Appendix B formula with five-layer defaults:

```
Layer Weights (five-layer defaults from Appendix B):
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

**Calculated score (Class A mode):** `___`  
**Calculated score (Class C mode):** `___`  
**Classification:** `___`  
**Does this score seem right given what you observed?** `___`

### 5.4 Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-004
Date:                [execution date]
Tool:                Cursor [version from Info.plist]
Scenario ID:         CUR-POS-01 (Standard IDE session + AI edit + agentic task)
Environment:         [OS version, endpoint posture, network topology]
Scenario Type:       Positive

Signal Observations:
  Process:           [observed / not observed — cite evidence files]
  File/Artifact:     [observed / not observed — cite evidence files]
  Network:           [observed / not observed — cite evidence files]
  Identity:          [observed / not observed — cite evidence files]
  Behavior:          [observed / not observed — cite evidence files]

Confidence Result:   [score + rationale, separate for Class A and Class C modes]
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

## Evidence Inventory Checklist

When complete, `$LAB_DIR` should contain:

```
LAB-RUN-004/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── cursor-global-dir.txt
│   ├── cursor-global-dir-recursive.txt
│   ├── workspace-cursor-dirs.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── cursor-processes.txt
│   ├── cursor-helper-processes.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── cursor-network.txt
│   ├── env-vars.txt
│   ├── cursor-env.txt
│   ├── launch-agents.txt
│   ├── cursor-plist-check.txt
│   ├── crontab.txt
│   ├── login-items.txt
│   ├── cursor-binary-listing.txt
│   ├── cursor-binary-type.txt
│   ├── cursor-codesign.txt
│   ├── cursor-binary-hash.txt
│   ├── cursor-version.txt
│   └── *.bak (shell profile backups)
├── phase1-footprint/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── app-bundle-structure.txt         ← binary analysis
│   ├── app-bundle-size.txt
│   ├── frameworks.txt                   ← Electron/Chromium frameworks
│   ├── cursor-global-full.txt           ← full ~/.cursor/ listing
│   ├── cursor-global-dirs.txt
│   ├── cursor-global-stats.txt
│   ├── extensions-listing.txt           ← installed extensions
│   ├── extensions-inventory.txt
│   ├── user-settings.json               ← user preferences
│   ├── user-keybindings.json
│   ├── state-databases.txt              ← SQLite/vscdb state files
│   ├── ai-feature-artifacts.txt
│   ├── identity-artifacts.txt           ← auth/account state files
│   ├── storage-files.txt
│   ├── json-with-identity.txt
│   ├── workspace-cursor-dir.txt         ← project .cursor/ dir
│   ├── cursor-rules-files.txt
│   └── cursor-skills-files.txt
├── phase2-launch/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── cursor-all-processes.txt         ← full process inventory
│   ├── cursor-main-pid.txt
│   ├── cursor-process-tree.txt          ← process tree from main PID
│   ├── cursor-helpers.txt               ← helper/GPU/renderer processes
│   ├── cursor-resource-usage.txt
│   ├── cursor-network-all.txt           ← all network connections
│   ├── cursor-listening-ports.txt
│   ├── cursor-established.txt           ← outbound connections
│   ├── cursor-dest-ips.txt
│   ├── cursor-dest-dns.txt              ← reverse DNS of destinations
│   ├── extension-host.txt
│   ├── connections-stream.txt           ← ongoing monitor
│   ├── pstree-stream.txt               ← ongoing monitor
│   └── monitor-pids.txt
├── phase3a-classA/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── processes-before.txt
│   ├── network-before.txt
│   ├── cursor-dir-before.txt
│   ├── processes-after.txt
│   ├── network-after.txt
│   ├── new-files-classA.txt
│   ├── cursor-dir-after.txt
│   ├── cursor-dir-diff.txt              ← state changes during Class A
│   └── cursor-changed-files.txt
├── phase3b-classC/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt               ← 1-second resolution
│   ├── file-events.txt                  ← fswatch (if available)
│   ├── connections-stream.txt
│   ├── workspace-files.txt
│   ├── workspace-contents.txt           ← project file contents
│   ├── git-check.txt
│   ├── git-log.txt
│   ├── git-log-full.txt
│   ├── new-files-classC.txt
│   ├── cursor-dir-post-agentic.txt
│   ├── cursor-dir-diff.txt              ← state changes during Class C
│   ├── workspace-cursor-post.txt
│   ├── agent-session-artifacts.txt
│   └── cursor-changed-files.txt
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── cursor-processes-final.txt
│   ├── cursor-network-final.txt
│   ├── cursor-dir-final.txt
│   ├── cursor-dir-diff-from-baseline.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── cursor-changed-artifacts.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-final.txt
│   ├── launch-agents-diff.txt
│   ├── cursor-disk-usage.txt
│   └── cursor-app-disk-usage.txt
└── [Phase 5 analysis in LAB-RUN-004-RESULTS.md]
```

---

## Post-Run: Next Steps

1. **Complete the Phase 5 analysis** — fill in every cell of the observation matrix, the class escalation analysis, and calculate dual confidence scores (Class A and Class C modes).
2. **Derive Cursor-specific layer weights** — use observed signal strengths to propose calibrated weights. Compare against both Claude Code (Class C) and Ollama (Class B) calibrations.
3. **Update the Playbook Lab Run Log** (Section 12.5) with results.
4. **File playbook feedback** for any IOCs in Section 4.2 that were predicted incorrectly, missing, or need enhancement based on lab observations.
5. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
6. **Plan next run** — CUR-POS-02 (multi-file refactor + git workflow in agentic mode) or CUR-EVA-01 (wrapped launch path / proxy attribution evasion).
