# Lab Run Protocol: Open Interpreter Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-006  
**Tool:** Open Interpreter (`open-interpreter`)  
**Class:** C (Autonomous Executor)  
**Playbook Reference:** Section 4.7 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Standard venv install, first launch, agentic command execution with direct shell access  
**Scenario ID:** OI-POS-01  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | macOS 26.3, ARM64 (Apple Silicon M2) |
| **Python** | Python 3 with `venv` module |
| **Shell** | zsh |
| **Root/sudo** | Required for `tcpdump` (optional — capture what we can without it) |
| **Disk** | Sufficient space for evidence artifacts and virtualenv (~500 MB headroom) |
| **Network** | Outbound internet access (PyPI for install, model provider API for runtime) |
| **API Key** | `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in environment. Fallback: `interpreter --local` using Ollama (installed from LAB-RUN-003) |

### Tool Availability Check

Run before starting. All must be present:

```bash
python3 --version
python3 -m venv --help >/dev/null 2>&1 && echo "venv available"
which pip3
which pstree         # process tree viewer (brew install pstree)
which lsof           # port/connection inspection
which shasum         # evidence hashing
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/oi-lab/LAB-RUN-006
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3-agentic,phase4-teardown}
```

---

## Pre-Install: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer so each subsequent phase produces a meaningful diff.

### File System Baseline

```bash
# Home directory tree (depth-limited)
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  -not -path '*/oi-lab/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

# Confirm no pre-existing Open Interpreter artifacts
ls -la ~/oi-lab-venv 2>&1 > "$LAB_DIR/baseline/venv-check.txt"
find ~ -name '*open-interpreter*' -o -name '*open_interpreter*' 2>/dev/null \
  > "$LAB_DIR/baseline/oi-artifact-scan.txt"

# Check XDG/config paths for Open Interpreter state
ls -la ~/.config/open-interpreter/ 2>&1 > "$LAB_DIR/baseline/oi-config-check.txt"
ls -la ~/.local/share/open-interpreter/ 2>&1 >> "$LAB_DIR/baseline/oi-config-check.txt"

# /tmp state
ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"

# Shell profile snapshots
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename $f).bak"
done
```

### Process Baseline

```bash
ps auxww > "$LAB_DIR/baseline/ps-full.txt"
pstree > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || ps auxf > "$LAB_DIR/baseline/ps-tree.txt"

# Confirm no interpreter process running
ps auxww | grep -i 'interpreter\|open.interpreter' | grep -v grep \
  > "$LAB_DIR/baseline/oi-process-check.txt" 2>&1
echo "Matching processes: $(wc -l < "$LAB_DIR/baseline/oi-process-check.txt")" \
  >> "$LAB_DIR/baseline/oi-process-check.txt"
```

### Network Baseline

```bash
lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt" 2>/dev/null
lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt" 2>/dev/null
```

### Environment Baseline

```bash
env | sort > "$LAB_DIR/baseline/env-vars.txt"

# API key presence check (existence, not value — do NOT log the key itself)
env | grep -i 'OPENAI_API_KEY\|ANTHROPIC_API_KEY' | sed 's/=.*/=<REDACTED>/' \
  > "$LAB_DIR/baseline/api-key-check.txt" 2>/dev/null
echo "Exit code: $? (1 = no API keys found)" >> "$LAB_DIR/baseline/api-key-check.txt"

# pip global packages
pip3 list 2>/dev/null > "$LAB_DIR/baseline/pip-globals.txt"

# Check for interpreter entrypoint
which interpreter > "$LAB_DIR/baseline/which-interpreter.txt" 2>&1
echo "Exit code: $? (1 = not found, expected)" >> "$LAB_DIR/baseline/which-interpreter.txt"
```

### Persistence Mechanism Baseline

```bash
# macOS: LaunchAgents
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1
```

### Identity Baseline

```bash
whoami > "$LAB_DIR/baseline/identity.txt"
id >> "$LAB_DIR/baseline/identity.txt"
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

**Purpose:** Capture the full installation footprint — virtualenv creation, pip package download, files placed, network connections to PyPI, entrypoint discovery, and package metadata.

> **Key difference from Claude Code (Class C):** Installation is via `pip` into an isolated virtualenv, not `npm -g`. The install footprint is contained within the virtualenv directory, not scattered across global paths. The entrypoint `interpreter` is a console_script in the venv's `bin/`.

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

### Create Virtualenv and Install

```bash
# Create isolated virtualenv
python3 -m venv ~/oi-lab-venv 2>&1 | tee "$LAB_DIR/phase1-install/venv-create-output.txt"
echo "Venv create exit code: $?" >> "$LAB_DIR/phase1-install/venv-create-output.txt"

# Activate
source ~/oi-lab-venv/bin/activate

# Capture pip version
pip --version > "$LAB_DIR/phase1-install/pip-version.txt" 2>&1

# Install Open Interpreter with full output
pip install open-interpreter 2>&1 | tee "$LAB_DIR/phase1-install/pip-install-output.txt"
echo "Install exit code: $?" >> "$LAB_DIR/phase1-install/pip-install-output.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Post-Install Capture

```bash
# Entrypoint discovery
which interpreter > "$LAB_DIR/phase1-install/which-interpreter.txt" 2>&1

# Entrypoint metadata
INTERP_BIN=$(which interpreter 2>/dev/null)
if [ -n "$INTERP_BIN" ]; then
  ls -la "$INTERP_BIN" > "$LAB_DIR/phase1-install/binary-metadata.txt"
  file "$INTERP_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  head -5 "$INTERP_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt" 2>/dev/null
  shasum -a 256 "$INTERP_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
fi

# Version capture
interpreter --version > "$LAB_DIR/phase1-install/oi-version.txt" 2>&1 || \
  python -c "import interpreter; print(interpreter.__version__)" >> "$LAB_DIR/phase1-install/oi-version.txt" 2>&1

# Virtualenv structure
find ~/oi-lab-venv -maxdepth 3 -type f 2>/dev/null > "$LAB_DIR/phase1-install/venv-structure.txt"

# site-packages/interpreter/ contents — key file-layer IOC
ls -laR ~/oi-lab-venv/lib/python*/site-packages/interpreter/ \
  > "$LAB_DIR/phase1-install/interpreter-package-contents.txt" 2>&1

# Full pip package list in venv
pip list > "$LAB_DIR/phase1-install/pip-venv-packages.txt" 2>&1
pip list --format=json > "$LAB_DIR/phase1-install/pip-venv-packages.json" 2>&1

# Package metadata
pip show open-interpreter > "$LAB_DIR/phase1-install/pip-show-oi.txt" 2>&1

# Disk usage of venv
du -sh ~/oi-lab-venv/ > "$LAB_DIR/phase1-install/venv-disk-usage.txt" 2>&1

# New files since baseline marker
find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -not -path '*/oi-lab/*' \
  -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt"

# Config directory check (did install create anything?)
ls -laR ~/.config/open-interpreter/ 2>&1 > "$LAB_DIR/phase1-install/oi-config-post.txt"
ls -laR ~/.local/share/open-interpreter/ 2>&1 >> "$LAB_DIR/phase1-install/oi-config-post.txt"

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
```

### Phase 1 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
shasum -a 256 "$LAB_DIR/phase1-install/"* > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 2: First Launch — Process Tree, Model Provider Connection, and Idle State

**Purpose:** Capture what happens when `interpreter` starts but before any agentic task — process lineage, model provider authentication, network connections at idle, and config/state file creation.

> **Key difference from Claude Code (Class C):** Open Interpreter is a Python process, not Node.js. The process tree is: terminal → python → interpreter module. There is no browser-based OAuth flow — authentication is via API key env vars passed to the model provider SDK. The model provider endpoint (OpenAI, Anthropic, or local Ollama) determines the network target.

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

### Ensure Virtualenv is Active

```bash
source ~/oi-lab-venv/bin/activate
```

### Launch Open Interpreter

Determine the model provider and launch accordingly:

```bash
# Check for API keys
if [ -n "$OPENAI_API_KEY" ]; then
  echo "Using OpenAI backend" > "$LAB_DIR/phase2-launch/model-backend.txt"
  interpreter --version 2>&1 | tee "$LAB_DIR/phase2-launch/launch-output.txt"
elif [ -n "$ANTHROPIC_API_KEY" ]; then
  echo "Using Anthropic backend" > "$LAB_DIR/phase2-launch/model-backend.txt"
  interpreter --version 2>&1 | tee "$LAB_DIR/phase2-launch/launch-output.txt"
else
  echo "No cloud API key — attempting local mode via Ollama" > "$LAB_DIR/phase2-launch/model-backend.txt"
  # Start Ollama if not running
  ollama serve &
  sleep 3
  interpreter --local --version 2>&1 | tee "$LAB_DIR/phase2-launch/launch-output.txt"
fi
```

### Capture Process State at Launch

```bash
# Process tree of the interpreter
ps auxww | grep -E 'interpreter|open.interpreter' | grep -v grep \
  > "$LAB_DIR/phase2-launch/oi-processes.txt"

# Full python process details
ps auxww | grep -E 'python.*interpreter' | grep -v grep \
  >> "$LAB_DIR/phase2-launch/oi-processes.txt"

# Outbound connections
lsof -i -nP > "$LAB_DIR/phase2-launch/outbound-at-launch.txt" 2>/dev/null

# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/phase2-launch/listening-ports-at-launch.txt" 2>/dev/null

# New files created on first launch
find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -not -path '*/oi-lab/*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/new-files-at-launch.txt"

# Config/state directory contents after first launch
ls -laR ~/.config/open-interpreter/ 2>&1 > "$LAB_DIR/phase2-launch/oi-config-at-launch.txt"
find ~ -path '*open-interpreter*' -o -path '*open_interpreter*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/oi-artifacts-at-launch.txt"

# Credential exposure check — does the API key appear in process args?
ps auxww | grep -i 'api.key\|OPENAI\|ANTHROPIC\|sk-' | grep -v grep \
  > "$LAB_DIR/phase2-launch/credential-exposure-check.txt" 2>/dev/null
echo "Lines found: $(wc -l < "$LAB_DIR/phase2-launch/credential-exposure-check.txt")" \
  >> "$LAB_DIR/phase2-launch/credential-exposure-check.txt"

# Privilege context
whoami > "$LAB_DIR/phase2-launch/privilege-context.txt"
id >> "$LAB_DIR/phase2-launch/privilege-context.txt"
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

## Phase 3: Agentic Session — Trigger Class C Behavioral Signals and Command-Chain Detection

**Purpose:** Validate the autonomous executor IOCs. Force Open Interpreter to execute shell commands, create files, install packages, and run tests — the command-chain signature that is Open Interpreter's primary risk signal. This is the most important phase.

> **Critical difference from Claude Code:** Open Interpreter executes shell commands DIRECTLY on the host. With `--auto_run` / `-y`, it skips all confirmation prompts. The child process chain (python → bash → pip/python/pytest) is the highest-risk behavior in the playbook. Capture process trees at ≤1-second intervals to catch transient child chains.

### Prepare a Clean Working Directory

```bash
mkdir -p ~/oi-lab-workspace && cd ~/oi-lab-workspace
```

### Start Background Monitors

```bash
# Terminal A: Process tree every 1 second (HIGH FREQUENCY — critical for command-chain capture)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-agentic/pstree-stream.txt"
  pstree >> "$LAB_DIR/phase3-agentic/pstree-stream.txt" 2>/dev/null
  sleep 1
done &
PS_PID=$!

# Terminal B: Targeted process capture every 500ms (Python + child chains)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-agentic/python-process-stream.txt"
  ps -eo pid,ppid,uid,comm,args | grep -E 'python|interpreter|bash|pip|pytest|flask' | grep -v grep \
    >> "$LAB_DIR/phase3-agentic/python-process-stream.txt"
  sleep 0.5
done &
FAST_PS_PID=$!

# Terminal C: Connection snapshots every 1 second
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-agentic/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase3-agentic/connections-stream.txt" 2>/dev/null
  sleep 1
done &
CONN_PID=$!

# Terminal D: File change watcher on workspace (macOS)
if which fswatch >/dev/null 2>&1; then
  fswatch ~/oi-lab-workspace > "$LAB_DIR/phase3-agentic/file-events.txt" &
  FSWATCH_PID=$!
fi
```

### Issue the Agentic Task

Use `interpreter -y` (auto-run) with explicit task string to avoid interactive TTY issues:

```bash
source ~/oi-lab-venv/bin/activate
cd ~/oi-lab-workspace

# Agentic task designed to trigger:
# - Plan→execute→revise loops (behavioral IOC)
# - Repeated shell/file operations with low inter-command delay (behavioral IOC)
# - Package install + execution chain in same loop (risk marker)
interpreter -y -e "Create a Python project with a Flask API that has a /hello endpoint returning JSON. Write tests using pytest. Install dependencies (flask, pytest), then run the tests. Put everything in ~/oi-lab-workspace." \
  2>&1 | tee "$LAB_DIR/phase3-agentic/agentic-session-output.txt"

echo "Interpreter exit code: $?" >> "$LAB_DIR/phase3-agentic/agentic-session-output.txt"
```

**During execution, observe and note:**

1. **Permission prompts** — With `-y`, there should be none. Document this — auto-execution without confirmation is the highest-risk behavior.
2. **Command chain sequence** — Watch for: python → bash → pip install flask → python → pytest → result processing.
3. **Child processes** — The 500ms process monitor should capture: interpreter (python) → bash → pip/python/pytest chains.
4. **File creation burst** — Multiple files created in rapid succession.

### Post-Task Capture

```bash
# All files in workspace with timestamps
find ~/oi-lab-workspace -type f -ls > "$LAB_DIR/phase3-agentic/workspace-files.txt"

# File contents
for f in $(find ~/oi-lab-workspace -type f -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt" 2>/dev/null
  echo "" >> "$LAB_DIR/phase3-agentic/workspace-contents.txt"
done

# Files changed across all of home since Phase 2
find ~ -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" \
  -not -path '*/oi-lab/*' \
  2>/dev/null > "$LAB_DIR/phase3-agentic/new-files-during-agentic.txt"

# Config/state directory after agentic session
ls -laR ~/.config/open-interpreter/ 2>&1 > "$LAB_DIR/phase3-agentic/oi-config-post-agentic.txt"
find ~ -path '*open-interpreter*' -o -path '*open_interpreter*' \
  2>/dev/null > "$LAB_DIR/phase3-agentic/oi-artifacts-post-agentic.txt"

# Credential exposure re-check
ps auxww | grep -i 'api.key\|OPENAI\|ANTHROPIC\|sk-' | grep -v grep \
  > "$LAB_DIR/phase3-agentic/credential-exposure-post.txt" 2>/dev/null

# Privilege escalation check — did any child process use sudo?
grep -i 'sudo' "$LAB_DIR/phase3-agentic/python-process-stream.txt" \
  > "$LAB_DIR/phase3-agentic/privilege-escalation-check.txt" 2>/dev/null
echo "Sudo attempts found: $(wc -l < "$LAB_DIR/phase3-agentic/privilege-escalation-check.txt")" \
  >> "$LAB_DIR/phase3-agentic/privilege-escalation-check.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $FAST_PS_PID $CONN_PID $FSWATCH_PID 2>/dev/null
```

### Phase 3 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3-agentic/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3-agentic/phase3-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3-agentic/"* > "$LAB_DIR/phase3-agentic/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Session End — What Persists After Exit

**Purpose:** Determine what survives after the Open Interpreter session ends and the virtualenv is deactivated. Key question: do session artifacts persist in ephemeral virtualenv context, or are there artifacts outside the venv (XDG config paths, shell history, cached state)?

### Deactivate and Capture

```bash
deactivate 2>/dev/null

# Wait for cleanup
sleep 5

# Process check: is anything still running?
ps auxww | grep -E 'interpreter|open.interpreter' | grep -v grep \
  > "$LAB_DIR/phase4-teardown/remaining-processes.txt"
echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt")" \
  >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"

# Orphan child processes?
pstree > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null

# Lingering network connections
lsof -i -nP > "$LAB_DIR/phase4-teardown/connections-post-exit.txt" 2>/dev/null
diff "$LAB_DIR/baseline/active-connections.txt" \
  "$LAB_DIR/phase4-teardown/connections-post-exit.txt" \
  > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1

# Listening ports
lsof -i -nP | grep LISTEN > "$LAB_DIR/phase4-teardown/listening-ports-post.txt" 2>/dev/null

# Persistent files — what exists outside the venv?
ls -laR ~/.config/open-interpreter/ 2>&1 > "$LAB_DIR/phase4-teardown/oi-config-final.txt"
find ~ -path '*open-interpreter*' -o -path '*open_interpreter*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/oi-artifacts-final.txt"

# Full diff: what files exist now that didn't at baseline?
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  -not -path '*/oi-lab/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt"

# Virtualenv persistence check
ls -la ~/oi-lab-venv/ > "$LAB_DIR/phase4-teardown/venv-persistence.txt" 2>&1
du -sh ~/oi-lab-venv/ >> "$LAB_DIR/phase4-teardown/venv-persistence.txt" 2>&1

# Session/history artifacts
find ~/oi-lab-venv -name '*.log' -o -name '*.history' -o -name '*.json' \
  2>/dev/null | head -50 > "$LAB_DIR/phase4-teardown/venv-session-artifacts.txt"

# Workspace persistence
ls -laR ~/oi-lab-workspace/ > "$LAB_DIR/phase4-teardown/workspace-final.txt" 2>&1

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

# macOS: LaunchAgents
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1

# Evasion observation: what survives venv deletion?
# (Do NOT delete the venv yet — just document what would survive)
echo "=== Artifacts OUTSIDE venv (would survive deletion) ===" \
  > "$LAB_DIR/phase4-teardown/evasion-observations.txt"
find ~ -path '*open-interpreter*' -o -path '*open_interpreter*' \
  2>/dev/null | grep -v 'oi-lab-venv' \
  >> "$LAB_DIR/phase4-teardown/evasion-observations.txt"
echo "" >> "$LAB_DIR/phase4-teardown/evasion-observations.txt"
echo "=== Ease of hiding ===" >> "$LAB_DIR/phase4-teardown/evasion-observations.txt"
echo "Virtualenv can be created anywhere with any name." >> "$LAB_DIR/phase4-teardown/evasion-observations.txt"
echo "Entrypoint 'interpreter' can be renamed or invoked via 'python -m interpreter'." \
  >> "$LAB_DIR/phase4-teardown/evasion-observations.txt"
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

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.7:

| Layer | IOC (from Section 4.7) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | Python runtime mapped to Open Interpreter entrypoints/modules | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Parent lineage: terminal/script → open-interpreter → child command chains | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Privilege context: effective uid/admin elevation during sessions | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `open-interpreter` package in venv/site-packages | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Session history/transcript artifacts | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Short-window file write bursts aligned with command execution | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Model-provider API calls with burst timing matching action loops | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Outbound requests triggered as part of command workflows | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | Endpoint user identity mapped to interpreter runtime session | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | Credential/token exposure in runtime environment | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Plan→execute→revise loops with command bursts | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Repeated shell/file operations with low inter-command delay | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Package install + execution chain in same loop | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Credential-store touches / broad file fan-out in restricted paths | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

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

### 5.3 Completed Lab Run Evidence Template

```
Run ID:              LAB-RUN-006
Date:                [execution date]
Tool:                Open Interpreter [version]
Scenario ID:         OI-POS-01 (Standard venv install + interactive session + agentic command execution)
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

### 5.4 Class C Cross-Comparison (Open Interpreter vs Claude Code)

| Dimension | Claude Code | Open Interpreter | Significance |
|---|---|---|---|
| Process model | Node.js (`node` → `cli.js`) | Python (`python` → `interpreter` module) | Different detection rules needed — `node.*claude` won't catch Python-based Class C tools |
| Permission model | Interactive confirmation before shell execution | Can auto-execute with `-y` / `--auto_run` | Open Interpreter has weaker safety boundary |
| Identity signals | OAuth profile in `~/.claude/backups/` | API key env var (if set) | Different identity anchor — env var vs stored credential |
| File footprint | 308 files in `~/.claude/` | Contained in venv + workspace | Open Interpreter may have smaller persistent footprint |
| Persistence | Zero active persistence | Zero active persistence (both are on-demand CLI) | Similar — neither installs daemons |
| Network pattern | Short-lived HTTPS to `api.anthropic.com` | Short-lived HTTPS to model provider (varies) | Similar challenge for polling-based capture |
| Child processes | claude → shell → git/python | python → bash → pip/python/pytest | Both produce transient child chains requiring <1s monitoring |

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
LAB-RUN-006/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── venv-check.txt
│   ├── oi-artifact-scan.txt
│   ├── oi-config-check.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── oi-process-check.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── env-vars.txt
│   ├── api-key-check.txt
│   ├── pip-globals.txt
│   ├── which-interpreter.txt
│   ├── launch-agents.txt
│   ├── crontab.txt
│   ├── identity.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── venv-create-output.txt
│   ├── pip-version.txt
│   ├── pip-install-output.txt          ← full install log
│   ├── which-interpreter.txt
│   ├── binary-metadata.txt             ← entrypoint hash, type
│   ├── oi-version.txt
│   ├── venv-structure.txt              ← virtualenv file tree
│   ├── interpreter-package-contents.txt ← site-packages/interpreter/
│   ├── pip-venv-packages.txt           ← full dependency list
│   ├── pip-venv-packages.json
│   ├── pip-show-oi.txt                 ← package metadata
│   ├── venv-disk-usage.txt
│   ├── new-files.txt
│   ├── oi-config-post.txt
│   ├── ps-stream.txt
│   ├── connections-stream.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-post.txt
│   └── crontab-diff.txt
├── phase2-launch/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── model-backend.txt               ← which provider was used
│   ├── launch-output.txt
│   ├── connections-stream.txt
│   ├── pstree-stream.txt
│   ├── oi-processes.txt
│   ├── outbound-at-launch.txt
│   ├── listening-ports-at-launch.txt
│   ├── new-files-at-launch.txt
│   ├── oi-config-at-launch.txt
│   ├── oi-artifacts-at-launch.txt
│   ├── credential-exposure-check.txt   ← API key in process args?
│   └── privilege-context.txt
├── phase3-agentic/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── agentic-session-output.txt      ← full session transcript
│   ├── pstree-stream.txt               ← 1-second resolution
│   ├── python-process-stream.txt       ← 500ms targeted capture
│   ├── connections-stream.txt
│   ├── file-events.txt                 ← fswatch (if available)
│   ├── workspace-files.txt
│   ├── workspace-contents.txt
│   ├── new-files-during-agentic.txt
│   ├── oi-config-post-agentic.txt
│   ├── oi-artifacts-post-agentic.txt
│   ├── credential-exposure-post.txt
│   └── privilege-escalation-check.txt
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── remaining-processes.txt
│   ├── pstree-post-exit.txt
│   ├── connections-post-exit.txt
│   ├── connections-diff.txt
│   ├── listening-ports-post.txt
│   ├── oi-config-final.txt
│   ├── oi-artifacts-final.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── venv-persistence.txt            ← virtualenv survival
│   ├── venv-session-artifacts.txt
│   ├── workspace-final.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-final.txt
│   ├── launch-agents-diff.txt
│   └── evasion-observations.txt        ← evasion surface notes
└── [Phase 5 analysis filled in manually or in a separate doc]
```

---

## Post-Run: Next Steps

1. **Complete the Section 5 analysis** — fill in every cell of the observation matrix, the Class C cross-comparison, and calculate the confidence score.
2. **Compare against Claude Code (LAB-RUN-001)** — both are Class C. Test whether the weight profiles are generalizable or tool-specific.
3. **Update the Playbook Lab Run Log** (Section 12.5) with results.
4. **File playbook feedback** for any IOCs in Section 4.7 that were predicted incorrectly or missing.
5. **Propose Open Interpreter-specific layer weights** — use observed signal strengths to calibrate.
6. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
7. **Plan next run** — OI-POS-02 (multi-step automation with restricted paths) or OI-EVA-01 (wrapped launch, ephemeral venv).
