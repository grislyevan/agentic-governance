# Lab Run Protocol: GitHub Copilot Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-005  
**Tool:** GitHub Copilot (`GitHub.copilot`, `GitHub.copilot-chat` VS Code extensions)  
**Class:** A (SaaS Copilot / Assistive IDE Feature)  
**Playbook Reference:** Section 4.3 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Standard VS Code session + Copilot inline suggestions + chat-assisted editing  
**Scenario ID:** CP-POS-01  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | macOS 26.3, ARM64 (Apple Silicon M2) |
| **Host IDE** | VS Code (installed via `brew install --cask visual-studio-code`). NOT Cursor — Cursor must not be running during capture to isolate Copilot signals. |
| **Shell** | zsh |
| **Root/sudo** | Not available. Use `lsof`, `ps`, and process tree tools for network/process capture. |
| **Disk** | Sufficient space for evidence artifacts (~500 MB headroom) |
| **Network** | Outbound internet access (VS Code marketplace, GitHub Copilot API) |
| **GitHub Account** | Required for Copilot authentication. Active Copilot subscription (individual, business, or enterprise). If unavailable, capture the denial state — it is itself evidence. |

### Tool Availability Check

Run before starting. All must be present:

```bash
which brew            # required for VS Code install
which lsof            # port/connection inspection
which pstree          # process tree viewer (brew install pstree)
which shasum          # evidence hashing
which script          # terminal session recorder (macOS built-in)
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/copilot-lab/LAB-RUN-005
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3a-completions,phase3b-chat,phase3c-agent,phase4-teardown}
```

---

## Pre-Install: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer so each subsequent phase produces a meaningful diff. This baseline captures the state BEFORE VS Code and Copilot are installed.

### File System Baseline

```bash
# Home directory tree (depth-limited)
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

# Confirm no pre-existing Copilot extension artifacts
ls -la ~/.vscode/extensions/ 2>&1 > "$LAB_DIR/baseline/vscode-extensions-check.txt"
find ~/.vscode -name '*copilot*' -o -name '*GitHub.copilot*' 2>/dev/null \
  > "$LAB_DIR/baseline/copilot-artifact-scan.txt"

# VS Code user data directory check
ls -la ~/Library/Application\ Support/Code/ 2>&1 > "$LAB_DIR/baseline/vscode-appdata-check.txt"

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

# Confirm no VS Code or Copilot processes running
ps auxww | grep -iE 'code|copilot|electron' | grep -v grep > "$LAB_DIR/baseline/vscode-process-check.txt" 2>&1
echo "Matching processes: $(wc -l < "$LAB_DIR/baseline/vscode-process-check.txt")" \
  >> "$LAB_DIR/baseline/vscode-process-check.txt"
```

### Network Baseline

```bash
# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt" 2>&1

# Active outbound connections
lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt" 2>&1
```

### Environment Baseline

```bash
# Full environment dump
env | sort > "$LAB_DIR/baseline/env-vars.txt"

# GitHub/Copilot-specific env check
env | grep -iE 'github|copilot' > "$LAB_DIR/baseline/github-env.txt" 2>/dev/null
echo "Exit code: $? (1 = no GITHUB/COPILOT vars found, expected)" >> "$LAB_DIR/baseline/github-env.txt"

# VS Code CLI check
which code > "$LAB_DIR/baseline/which-code.txt" 2>&1
echo "Exit code: $? (1 = not found, expected pre-install)" >> "$LAB_DIR/baseline/which-code.txt"
```

### Persistence Mechanism Baseline

```bash
# macOS LaunchAgents
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1
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

## Phase 1: Installation — VS Code + Copilot Extension Install

**Purpose:** Capture the full installation footprint — VS Code app install (if needed), Copilot extension install via marketplace, files created, network connections made, and extension manifests placed on disk.

> **Key difference from Class B/C tools:** Copilot is not a standalone binary or daemon. Installation is an IDE extension install via the VS Code marketplace. The "binary" is the VS Code app; the "tool" is an extension bundle inside it. Phase 1 captures BOTH the IDE install and the extension install as separate steps.

### Start Background Monitors

```bash
# Terminal A: Process monitor (snapshot every 2 seconds)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase1-install/ps-stream.txt"
  ps auxww >> "$LAB_DIR/phase1-install/ps-stream.txt"
  sleep 2
done &
PS_PID=$!

# Terminal B: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase1-install/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase1-install/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!
```

### Step 1A: Install VS Code (if not already present)

```bash
# Install VS Code via Homebrew
brew install --cask visual-studio-code 2>&1 | \
  tee "$LAB_DIR/phase1-install/vscode-install-output.txt"

echo "VS Code install exit code: $?" >> "$LAB_DIR/phase1-install/vscode-install-output.txt"
echo "Install method: brew cask" >> "$LAB_DIR/phase1-install/vscode-install-output.txt"
```

### Step 1A Post-Install Capture

```bash
# VS Code binary discovery
which code > "$LAB_DIR/phase1-install/which-code.txt" 2>&1
code --version > "$LAB_DIR/phase1-install/vscode-version.txt" 2>&1

# VS Code app metadata
ls -la /Applications/Visual\ Studio\ Code.app 2>&1 > "$LAB_DIR/phase1-install/vscode-app-metadata.txt"
file /Applications/Visual\ Studio\ Code.app/Contents/MacOS/Electron >> "$LAB_DIR/phase1-install/vscode-app-metadata.txt" 2>&1

# Extension directory state before Copilot install
ls -la ~/.vscode/extensions/ 2>&1 > "$LAB_DIR/phase1-install/extensions-pre-copilot.txt"
```

### Step 1B: Install Copilot Extensions

```bash
# Install GitHub Copilot extension
code --install-extension GitHub.copilot 2>&1 | \
  tee "$LAB_DIR/phase1-install/copilot-extension-install.txt"

echo "Copilot install exit code: $?" >> "$LAB_DIR/phase1-install/copilot-extension-install.txt"

# Install GitHub Copilot Chat extension
code --install-extension GitHub.copilot-chat 2>&1 | \
  tee "$LAB_DIR/phase1-install/copilot-chat-extension-install.txt"

echo "Copilot Chat install exit code: $?" >> "$LAB_DIR/phase1-install/copilot-chat-extension-install.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Post-Install Capture

```bash
# Extension directory state after Copilot install
ls -laR ~/.vscode/extensions/GitHub.copilot* 2>&1 > "$LAB_DIR/phase1-install/copilot-extension-files.txt"

# Extension manifests — key File-layer IOC
find ~/.vscode/extensions -name 'package.json' -path '*copilot*' \
  -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase1-install/copilot-extension-manifests.txt"

# Extension version and metadata
code --list-extensions --show-versions 2>&1 > "$LAB_DIR/phase1-install/extension-list-post.txt"

# New files since baseline marker
find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -not -path '*/copilot-lab/*' \
  -not -path '*/.cache/*' \
  -not -path '*/node_modules/*' \
  2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt"

# VS Code user data directory
ls -laR ~/Library/Application\ Support/Code/ 2>&1 | head -200 \
  > "$LAB_DIR/phase1-install/vscode-appdata-post.txt"

# Shell profile diff
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

ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase1-install/launch-agents-post.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase1-install/launch-agents-post.txt" \
  > "$LAB_DIR/phase1-install/launch-agents-diff.txt" 2>&1
```

### Phase 1 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
shasum -a 256 "$LAB_DIR/phase1-install/"* > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 2: First Launch — VS Code + Copilot Active, Process Tree, Auth Flow

**Purpose:** Capture what happens when VS Code launches with Copilot active — process lineage (VS Code main → extension host → Copilot language server), authentication flow (GitHub OAuth redirect), network connections to Copilot endpoints, and initial file artifacts.

> **Key difference from Class B/C tools:** Copilot runs as a subprocess of the VS Code extension host, not as a standalone daemon or CLI. The process tree is: VS Code main (Electron) → extension host (node) → Copilot language server (node). Authentication is GitHub OAuth with browser redirect, not Anthropic OAuth or API keys.

### Start Background Monitors

```bash
# Terminal A: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase2-launch/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!

# Terminal B: Process tree snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
  pstree >> "$LAB_DIR/phase2-launch/pstree-stream.txt" 2>/dev/null || \
    ps auxf >> "$LAB_DIR/phase2-launch/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!
```

### Launch VS Code

```bash
# Open VS Code from the terminal (creates a capturable launch event)
open -a "Visual Studio Code" 2>&1 | tee "$LAB_DIR/phase2-launch/vscode-launch-output.txt"
# Wait for VS Code to fully initialize
sleep 10
```

### Capture VS Code + Copilot Process Tree

```bash
# Full process tree — look for Electron → extension host → copilot
ps auxww | grep -iE 'code|copilot|electron|extensionHost' | grep -v grep \
  > "$LAB_DIR/phase2-launch/vscode-copilot-processes.txt"

# Process tree rooted at VS Code main process
VSCODE_PID=$(pgrep -f 'Visual Studio Code' | head -1)
if [ -n "$VSCODE_PID" ]; then
  pstree -p "$VSCODE_PID" > "$LAB_DIR/phase2-launch/vscode-process-tree.txt" 2>/dev/null
  echo "VS Code main PID: $VSCODE_PID" >> "$LAB_DIR/phase2-launch/vscode-process-tree.txt"
fi

# All Electron/Code helper processes
ps auxww | grep -i 'Code Helper' | grep -v grep \
  > "$LAB_DIR/phase2-launch/code-helper-processes.txt"

# Copilot-specific subprocesses (language server, agent)
ps auxww | grep -iE 'copilot|github' | grep -v grep \
  > "$LAB_DIR/phase2-launch/copilot-subprocesses.txt"
```

### Capture Authentication State

```bash
# GitHub auth state — check for stored credentials
# macOS Keychain entries for GitHub/VS Code
security find-generic-password -s "github.com" 2>&1 | head -20 \
  > "$LAB_DIR/phase2-launch/github-keychain-check.txt"
security find-generic-password -s "vscodevscode.github-authentication" 2>&1 | head -20 \
  >> "$LAB_DIR/phase2-launch/github-keychain-check.txt"

# VS Code settings for GitHub auth
find ~/Library/Application\ Support/Code -name '*.json' -path '*User*' \
  -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null | head -500 > "$LAB_DIR/phase2-launch/vscode-user-settings.txt"

# GitHub authentication state files
find ~/Library/Application\ Support/Code -iname '*github*' -o -iname '*auth*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/github-auth-artifacts.txt"

# Copilot-specific state files
find ~/Library/Application\ Support/Code -iname '*copilot*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/copilot-state-files.txt"
```

### Capture Network State

```bash
# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/phase2-launch/listening-ports-at-launch.txt" 2>&1

# Outbound connections — look for GitHub/Copilot endpoints
lsof -i -nP > "$LAB_DIR/phase2-launch/outbound-at-launch.txt" 2>&1

# Filter for VS Code / Copilot-specific connections
lsof -i -nP | grep -iE 'code|copilot|electron' \
  > "$LAB_DIR/phase2-launch/vscode-network-connections.txt" 2>&1
```

### Capture File Artifacts

```bash
# New files created since Phase 1
find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -not -path '*/copilot-lab/*' \
  -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/new-files-at-launch.txt"

# Copilot extension runtime state
ls -laR ~/.vscode/extensions/GitHub.copilot* 2>&1 \
  > "$LAB_DIR/phase2-launch/copilot-extension-state.txt"

# VS Code logs (may contain Copilot initialization)
find ~/Library/Application\ Support/Code/logs -name '*.log' -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -exec echo "=== {} ===" \; -exec tail -50 {} \; \
  2>/dev/null > "$LAB_DIR/phase2-launch/vscode-logs.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Phase 2 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-launch/phase2-end-time.txt"
shasum -a 256 "$LAB_DIR/phase2-launch/"* > "$LAB_DIR/phase2-launch/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3A: Code Completion — Inline Suggestion Signals

**Purpose:** Validate the assistive code completion IOCs. Open a source file, type code, and observe Copilot inline suggestions — the suggestion-acceptance cadence that is the core Class A behavioral signal.

> **Key difference from Class C agentic sessions:** Copilot does NOT autonomously read files, write code, or execute shell commands during code completion. The signals here are about **suggestion frequency**, **acceptance cadence**, and **edit burst patterns** from accepted suggestions. The human remains the executor; Copilot is the assistant.

### Prepare a Working Directory

```bash
mkdir -p ~/copilot-lab-workspace && cd ~/copilot-lab-workspace

# Create a starter file for Copilot to suggest completions on
cat > ~/copilot-lab-workspace/app.py << 'PYEOF'
# Simple Flask application for testing Copilot suggestions

from flask import Flask

app = Flask(__name__)

# TODO: Add a route that returns a greeting
PYEOF
```

### Start Background Monitors

```bash
# Terminal A: Process tree every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3a-completions/pstree-stream.txt"
  ps auxww | grep -iE 'code|copilot|electron' | grep -v grep \
    >> "$LAB_DIR/phase3a-completions/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!

# Terminal B: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3a-completions/connections-stream.txt"
  lsof -i -nP | grep -iE 'code|copilot|electron' \
    >> "$LAB_DIR/phase3a-completions/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!

# Terminal C: File system watcher on workspace
fswatch ~/copilot-lab-workspace > "$LAB_DIR/phase3a-completions/file-events.txt" 2>/dev/null &
FSWATCH_PID=$!
```

### Open File in VS Code and Trigger Completions

```bash
# Open the workspace file in VS Code
code ~/copilot-lab-workspace/app.py
```

**Manual observation tasks (while typing in VS Code):**

1. **Position cursor** after the `# TODO` comment and start typing a route definition
2. **Observe** Copilot ghost text suggestions appearing
3. **Accept** a suggestion with Tab
4. **Type additional code** — observe suggestion cadence and quality
5. **Note** the time between typing and suggestion appearance (latency)

### Post-Completion Capture

```bash
# Workspace state after completions
find ~/copilot-lab-workspace -type f -ls > "$LAB_DIR/phase3a-completions/workspace-files.txt"

# Workspace file contents
for f in $(find ~/copilot-lab-workspace -type f -not -path '*/__pycache__/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3a-completions/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3a-completions/workspace-contents.txt"
  echo "" >> "$LAB_DIR/phase3a-completions/workspace-contents.txt"
done

# Copilot telemetry/logs generated during completions
find ~/Library/Application\ Support/Code -iname '*copilot*' -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" \
  2>/dev/null > "$LAB_DIR/phase3a-completions/copilot-files-during-completion.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID $FSWATCH_PID 2>/dev/null
```

### Phase 3A Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3a-completions/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3a-completions/phase3a-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3a-completions/"* > "$LAB_DIR/phase3a-completions/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3B: Copilot Chat — Chat-to-Edit Behavioral Sequence

**Purpose:** Validate the chat-assisted editing IOCs. Use the Copilot Chat panel to ask Copilot to explain code, generate a function, or refactor something. Capture the chat-to-edit behavioral sequence that is a higher-activity Class A signal.

### Start Background Monitors

```bash
# Terminal A: Process tree every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3b-chat/pstree-stream.txt"
  ps auxww | grep -iE 'code|copilot|electron' | grep -v grep \
    >> "$LAB_DIR/phase3b-chat/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!

# Terminal B: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3b-chat/connections-stream.txt"
  lsof -i -nP | grep -iE 'code|copilot|electron' \
    >> "$LAB_DIR/phase3b-chat/connections-stream.txt" 2>/dev/null
  sleep 2
done &
CONN_PID=$!
```

### Copilot Chat Tasks

**In VS Code, open the Copilot Chat panel and execute these tasks:**

1. **Explain code:** Select the Flask app code and ask Copilot to explain it
2. **Generate function:** Ask Copilot to "Add a `/users` route that returns a list of users as JSON"
3. **Refactor:** Ask Copilot to "Add error handling to all routes"

**Observe and note:**
- Chat response latency
- Whether Copilot proposes inline edits or just text responses
- Any file modifications initiated through the chat panel
- Process tree changes during chat interaction

### Post-Chat Capture

```bash
# Workspace state after chat interactions
find ~/copilot-lab-workspace -type f -ls > "$LAB_DIR/phase3b-chat/workspace-files.txt"

# Workspace file contents
for f in $(find ~/copilot-lab-workspace -type f -not -path '*/__pycache__/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3b-chat/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3b-chat/workspace-contents.txt"
  echo "" >> "$LAB_DIR/phase3b-chat/workspace-contents.txt"
done

# Diff against Phase 3A state
diff "$LAB_DIR/phase3a-completions/workspace-contents.txt" \
  "$LAB_DIR/phase3b-chat/workspace-contents.txt" \
  > "$LAB_DIR/phase3b-chat/workspace-diff.txt" 2>&1

# Copilot chat-specific artifacts
find ~/Library/Application\ Support/Code -iname '*copilot*' -newer "$LAB_DIR/phase3a-completions/TIMESTAMP_MARKER" \
  2>/dev/null > "$LAB_DIR/phase3b-chat/copilot-files-during-chat.txt"

# VS Code logs during chat
find ~/Library/Application\ Support/Code/logs -name '*.log' -newer "$LAB_DIR/phase3a-completions/TIMESTAMP_MARKER" \
  -exec echo "=== {} ===" \; -exec tail -50 {} \; \
  2>/dev/null > "$LAB_DIR/phase3b-chat/vscode-logs-during-chat.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Phase 3B Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3b-chat/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3b-chat/phase3b-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3b-chat/"* > "$LAB_DIR/phase3b-chat/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3C: Copilot Agent Mode (If Available)

**Purpose:** If the VS Code version supports Copilot's agent/edit mode, exercise it with a multi-file task. This would be the closest to Class C behavior — Copilot proposing multi-file edits, running terminal commands, or managing a workspace autonomously.

> **Note:** Copilot agent mode may not be available in all VS Code versions or subscription tiers. If unavailable, document the absence — this is useful evidence that Class A tools stay Class A under normal operation.

### If Agent Mode Available:

```bash
# Start monitors (same pattern as 3A/3B)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3c-agent/pstree-stream.txt"
  ps auxww | grep -iE 'code|copilot|electron' | grep -v grep \
    >> "$LAB_DIR/phase3c-agent/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!
```

**Task:** Ask Copilot (via agent mode) to "Add a test file for the Flask app with pytest, then add a requirements.txt."

**Observe:**
- Does Copilot create files autonomously or propose diffs for approval?
- Does it execute shell commands (pip install, pytest)?
- How does the process tree change during agent mode?

```bash
# Post-agent capture
find ~/copilot-lab-workspace -type f -ls > "$LAB_DIR/phase3c-agent/workspace-files.txt"
for f in $(find ~/copilot-lab-workspace -type f -not -path '*/__pycache__/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3c-agent/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3c-agent/workspace-contents.txt"
  echo "" >> "$LAB_DIR/phase3c-agent/workspace-contents.txt"
done

kill $PS_PID 2>/dev/null
```

### If Agent Mode NOT Available:

```bash
echo "Copilot agent mode not available in this VS Code version or subscription tier." \
  > "$LAB_DIR/phase3c-agent/agent-mode-status.txt"
echo "This confirms that Copilot remains Class A under normal operation." \
  >> "$LAB_DIR/phase3c-agent/agent-mode-status.txt"
code --version >> "$LAB_DIR/phase3c-agent/agent-mode-status.txt" 2>&1
```

### Phase 3C Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3c-agent/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3c-agent/phase3c-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3c-agent/"* > "$LAB_DIR/phase3c-agent/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Teardown — What Persists After VS Code Exits

**Purpose:** Determine what survives after VS Code is closed. Persistent state has forensic value — extension files, cached auth tokens, Copilot logs, and VS Code user data are key file-layer signals.

### Close VS Code

Quit VS Code via Cmd+Q or:

```bash
osascript -e 'quit app "Visual Studio Code"'
sleep 10
```

### Wait and Capture

```bash
# Process check: is anything still running?
ps auxww | grep -iE 'code|copilot|electron' | grep -v grep \
  > "$LAB_DIR/phase4-teardown/remaining-processes.txt"
echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt")" \
  >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"

# Orphan child processes?
pstree > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null

# Lingering network connections
lsof -i -nP > "$LAB_DIR/phase4-teardown/connections-post-exit.txt" 2>&1
diff "$LAB_DIR/baseline/active-connections.txt" \
  "$LAB_DIR/phase4-teardown/connections-post-exit.txt" \
  > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1

# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/phase4-teardown/listening-ports-post.txt" 2>&1

# Persistent extension files — key File-layer signal
ls -laR ~/.vscode/extensions/GitHub.copilot* 2>&1 \
  > "$LAB_DIR/phase4-teardown/copilot-extension-final.txt"

# VS Code user data — settings, state, logs
ls -laR ~/Library/Application\ Support/Code/ 2>&1 | head -500 \
  > "$LAB_DIR/phase4-teardown/vscode-appdata-final.txt"

# Copilot-specific persistent artifacts
find ~/Library/Application\ Support/Code -iname '*copilot*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/copilot-persistent-artifacts.txt"

# GitHub auth state persistence
find ~/Library/Application\ Support/Code -iname '*github*' -o -iname '*auth*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/github-auth-persistent.txt"

# Keychain auth persistence
security find-generic-password -s "vscodevscode.github-authentication" 2>&1 | head -20 \
  > "$LAB_DIR/phase4-teardown/keychain-auth-post.txt"

# Full diff: what files exist now that didn't at baseline?
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt"

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

ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1

# VS Code logs — check for Copilot-specific log entries
find ~/Library/Application\ Support/Code/logs -name '*.log' \
  -exec echo "=== {} ===" \; -exec grep -il 'copilot' {} \; \
  2>/dev/null > "$LAB_DIR/phase4-teardown/copilot-log-files.txt"
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

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.3:

| Layer | IOC (from Section 4.3) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | IDE host process (VS Code) + Copilot extension host subprocess | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Extension-host activity tied to chat/agent-style workflows | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Copilot extension install manifests (`extensions/GitHub.copilot*`) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Workspace extension settings, policy files, local logs/caches | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Traffic to `copilot-proxy.githubusercontent.com`, GitHub Copilot API endpoints | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Burst timing aligned with suggestion/chat activity | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | GitHub account auth state (org-managed vs personal) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | License/entitlement context from org policy | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Suggestion acceptance cadence + rapid edit bursts | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | AI-chat-to-edit sequences across multiple files | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | High-volume generated changes without normal review cadence | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

### 5.2 Confidence Score Calculation

Using Appendix B formula with five-layer defaults:

```
Layer Weights (five-layer defaults from Appendix B):
  Process:  0.30
  File:     0.20
  Network:  0.15
  Identity: 0.15
  Behavior: 0.20
```

> **Note:** Copilot does not yet have tool-specific calibrated weights. This lab run should produce the empirical data to derive them. Expect Identity to carry MORE weight for Class A tools than for Class B/C — the governance concern for Copilot is personal vs org-managed accounts, not autonomous execution.

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
  [ ] Extension-host process indistinguishable from other extensions: −0.05 (proposed, Class A-specific)

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

### 5.3 Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-005
Date:                [execution date]
Tool:                GitHub Copilot [version from extension list]
Scenario ID:         CP-POS-01 (Standard VS Code session + inline suggestions + chat)
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

### 5.4 Class A-Specific Analysis

Document these Class A characterization questions:

| Question | Finding |
|---|---|
| Does the extension run as a subprocess of the VS Code extension host? | |
| What is the full process tree: VS Code → extension host → Copilot? | |
| Does Copilot create any persistent files outside `~/.vscode/`? | |
| What GitHub auth state is stored locally? Where? | |
| Can we distinguish org-managed vs personal GitHub accounts from artifacts? | |
| Does Copilot make network connections only to GitHub-owned endpoints? | |
| Does Copilot stay Class A or can it escalate to Class C (agent mode)? | |
| What is the network connection pattern during suggestion vs chat? | |

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
LAB-RUN-005/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── vscode-extensions-check.txt
│   ├── copilot-artifact-scan.txt
│   ├── vscode-appdata-check.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── vscode-process-check.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── env-vars.txt
│   ├── github-env.txt
│   ├── which-code.txt
│   ├── launch-agents.txt
│   ├── crontab.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── vscode-install-output.txt           ← VS Code install log
│   ├── vscode-version.txt                  ← VS Code version
│   ├── vscode-app-metadata.txt             ← app binary metadata
│   ├── ps-stream.txt
│   ├── connections-stream.txt
│   ├── which-code.txt
│   ├── extensions-pre-copilot.txt
│   ├── copilot-extension-install.txt       ← Copilot extension install log
│   ├── copilot-chat-extension-install.txt  ← Copilot Chat install log
│   ├── copilot-extension-files.txt         ← extension file listing
│   ├── copilot-extension-manifests.txt     ← package.json contents
│   ├── extension-list-post.txt             ← all extensions with versions
│   ├── new-files.txt
│   ├── vscode-appdata-post.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-post.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-post.txt
│   └── launch-agents-diff.txt
├── phase2-launch/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── vscode-launch-output.txt
│   ├── connections-stream.txt
│   ├── pstree-stream.txt
│   ├── vscode-copilot-processes.txt        ← full process listing
│   ├── vscode-process-tree.txt             ← process tree from VS Code PID
│   ├── code-helper-processes.txt
│   ├── copilot-subprocesses.txt
│   ├── github-keychain-check.txt           ← auth credential state
│   ├── vscode-user-settings.txt
│   ├── github-auth-artifacts.txt
│   ├── copilot-state-files.txt
│   ├── listening-ports-at-launch.txt
│   ├── outbound-at-launch.txt
│   ├── vscode-network-connections.txt      ← Copilot network activity
│   ├── new-files-at-launch.txt
│   ├── copilot-extension-state.txt
│   └── vscode-logs.txt
├── phase3a-completions/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt
│   ├── connections-stream.txt
│   ├── file-events.txt                     ← filesystem watcher
│   ├── workspace-files.txt
│   ├── workspace-contents.txt
│   └── copilot-files-during-completion.txt
├── phase3b-chat/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt
│   ├── connections-stream.txt
│   ├── workspace-files.txt
│   ├── workspace-contents.txt
│   ├── workspace-diff.txt
│   ├── copilot-files-during-chat.txt
│   └── vscode-logs-during-chat.txt
├── phase3c-agent/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── agent-mode-status.txt               ← (if agent mode unavailable)
│   ├── pstree-stream.txt                   ← (if agent mode exercised)
│   ├── workspace-files.txt                 ← (if agent mode exercised)
│   └── workspace-contents.txt              ← (if agent mode exercised)
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── remaining-processes.txt
│   ├── pstree-post-exit.txt
│   ├── connections-post-exit.txt
│   ├── connections-diff.txt
│   ├── listening-ports-post.txt
│   ├── copilot-extension-final.txt         ← persistent extension files
│   ├── vscode-appdata-final.txt
│   ├── copilot-persistent-artifacts.txt
│   ├── github-auth-persistent.txt          ← auth state persistence
│   ├── keychain-auth-post.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-final.txt
│   ├── launch-agents-diff.txt
│   └── copilot-log-files.txt
└── [Phase 5 analysis in LAB-RUN-005-RESULTS.md]
```

---

## Post-Run: Next Steps

1. **Complete the Section 5 analysis** — fill in every cell of the observation matrix, the Class A characterization table, and calculate the confidence score.
2. **Derive Copilot-specific layer weights** — use observed signal strengths to propose calibrated weights for Class A tools (compare against Appendix B defaults and Class B/C calibrations).
3. **Update the Playbook Lab Run Log** (Section 12.5) with results.
4. **File playbook feedback** for any IOCs in Section 4.3 that were predicted incorrectly or missing.
5. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
6. **Plan next run** — CP-POS-02 (chat-assisted multi-file edit) or CP-EVA-01 (personal account on managed endpoint).
