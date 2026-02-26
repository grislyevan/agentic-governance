# Lab Run Protocol: Ollama Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-003  
**Tool:** Ollama (`ollama`)  
**Class:** B (Local Model Runtime)  
**Playbook Reference:** Section 4.4 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Standard install, daemon start, model pull, inference session, local API usage  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | Linux VPS (Ubuntu 22.04+ recommended) or macOS (native) |
| **Shell** | bash or zsh |
| **Root/sudo** | Required for `tcpdump`, `strace` (Linux), and service management |
| **Disk** | Sufficient space for evidence artifacts and at least one model (~5 GB headroom recommended) |
| **Network** | Outbound internet access (Ollama installer, `registry.ollama.ai` for model pulls) |
| **curl / brew** | `curl` required for Linux install script; `brew` optional for macOS |

### Tool Availability Check

Run before starting. All must be present:

```bash
which curl           # required for install (Linux) and API testing
which tcpdump        # needs sudo
which strace         # Linux only; macOS uses dtrace/dtruss
which script         # terminal session recorder
which pstree         # process tree viewer (install: apt install psmisc / brew install pstree)
which lsof           # port/connection inspection
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/ollama-lab/LAB-RUN-003
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-launch,phase3-inference,phase4-teardown}
```

---

## Pre-Install: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer so each subsequent phase produces a meaningful diff.

### File System Baseline

```bash
# Home directory tree (depth-limited to keep it manageable)
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

# Specifically confirm no pre-existing Ollama artifacts
ls -la ~/.ollama 2>&1 > "$LAB_DIR/baseline/ollama-dir-check.txt"
find ~ -name '*ollama*' 2>/dev/null \
  > "$LAB_DIR/baseline/ollama-artifact-scan.txt"

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

# Confirm no ollama process is already running
ps auxww | grep -i ollama | grep -v grep > "$LAB_DIR/baseline/ollama-process-check.txt" 2>&1
echo "Matching processes: $(wc -l < "$LAB_DIR/baseline/ollama-process-check.txt")" \
  >> "$LAB_DIR/baseline/ollama-process-check.txt"
```

### Network Baseline

```bash
# Listening ports (confirm port 11434 is not already in use)
ss -tlnp > "$LAB_DIR/baseline/listening-ports.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"

# Active outbound connections
ss -tnp > "$LAB_DIR/baseline/active-connections.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"

# Explicit check for port 11434
lsof -i :11434 > "$LAB_DIR/baseline/port-11434-check.txt" 2>&1
echo "Exit code: $? (1 = port not in use, expected)" >> "$LAB_DIR/baseline/port-11434-check.txt"
```

### Environment Baseline

```bash
# Full environment dump
env | sort > "$LAB_DIR/baseline/env-vars.txt"

# Ollama-specific env check
env | grep -i ollama > "$LAB_DIR/baseline/ollama-env.txt" 2>/dev/null
echo "Exit code: $? (1 = no OLLAMA vars found, expected)" >> "$LAB_DIR/baseline/ollama-env.txt"

# PATH check for ollama
which ollama > "$LAB_DIR/baseline/which-ollama.txt" 2>&1
echo "Exit code: $? (1 = not found, expected)" >> "$LAB_DIR/baseline/which-ollama.txt"
```

### Persistence Mechanism Baseline

```bash
# Linux: systemd services, crontab
systemctl list-units --type=service | grep -i ollama > "$LAB_DIR/baseline/ollama-service-check.txt" 2>/dev/null
systemctl --user list-units --type=service > "$LAB_DIR/baseline/user-services.txt" 2>/dev/null
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1

# macOS: LaunchAgents and LaunchDaemons
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
ls -la /Library/LaunchDaemons/ > "$LAB_DIR/baseline/launch-daemons.txt" 2>/dev/null
# Ollama-specific plist check
find ~/Library/LaunchAgents /Library/LaunchDaemons -name '*ollama*' \
  2>/dev/null > "$LAB_DIR/baseline/ollama-plist-check.txt"
echo "Exit code: $? (1 = none found, expected)" >> "$LAB_DIR/baseline/ollama-plist-check.txt"
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

**Purpose:** Capture the full installation footprint — files created, network connections made, binaries placed, service/daemon registration, and any persistence mechanisms established during install.

> **Key difference from Class C tools:** Ollama's installer typically registers a system daemon or LaunchAgent. This is the first major persistence signal and a defining characteristic of Class B local runtimes.

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

Choose the appropriate method for your platform:

**macOS (Homebrew):**

```bash
brew install ollama 2>&1 | \
  tee "$LAB_DIR/phase1-install/install-output.txt"

echo "Install exit code: $?" >> "$LAB_DIR/phase1-install/install-output.txt"
echo "Install method: brew" >> "$LAB_DIR/phase1-install/install-output.txt"
```

**macOS (Direct download) — alternative:**

```bash
# Download the macOS app from ollama.com
curl -fsSL https://ollama.com/download/Ollama-darwin.zip \
  -o "$LAB_DIR/phase1-install/Ollama-darwin.zip" 2>&1 | \
  tee "$LAB_DIR/phase1-install/download-output.txt"

echo "Download exit code: $?" >> "$LAB_DIR/phase1-install/download-output.txt"
echo "Install method: direct download (manual install required)" >> "$LAB_DIR/phase1-install/install-output.txt"
```

**Linux (Install script):**

```bash
curl -fsSL https://ollama.com/install.sh | sh 2>&1 | \
  tee "$LAB_DIR/phase1-install/install-output.txt"

echo "Install exit code: $?" >> "$LAB_DIR/phase1-install/install-output.txt"
echo "Install method: install.sh" >> "$LAB_DIR/phase1-install/install-output.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $DNS_PID 2>/dev/null
sudo kill $TCPDUMP_PID 2>/dev/null
```

### Post-Install Capture

```bash
# Binary discovery
which ollama > "$LAB_DIR/phase1-install/which-ollama.txt" 2>&1

# Binary metadata and hash
OLLAMA_BIN=$(which ollama 2>/dev/null)
if [ -n "$OLLAMA_BIN" ]; then
  ls -la "$OLLAMA_BIN" > "$LAB_DIR/phase1-install/binary-metadata.txt"
  file "$OLLAMA_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  readlink -f "$OLLAMA_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt" 2>/dev/null
  shasum -a 256 "$OLLAMA_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
fi

# Version capture
ollama --version > "$LAB_DIR/phase1-install/ollama-version.txt" 2>&1

# Ollama data directory (may not exist until first run)
ls -laR ~/.ollama 2>&1 > "$LAB_DIR/phase1-install/ollama-dir-post.txt"

# New files since baseline marker
find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -not -path '*/ollama-lab/*' \
  -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt"

# Persistence mechanism check — THIS IS A KEY CLASS B SIGNAL
# Linux: did the installer create a systemd service?
systemctl list-units --type=service | grep -i ollama > "$LAB_DIR/phase1-install/ollama-systemd-check.txt" 2>/dev/null
systemctl cat ollama.service > "$LAB_DIR/phase1-install/ollama-service-unit.txt" 2>/dev/null
ls -la /etc/systemd/system/ollama* > "$LAB_DIR/phase1-install/ollama-systemd-files.txt" 2>/dev/null

# macOS: did the installer register a LaunchAgent or LaunchDaemon?
ls -la ~/Library/LaunchAgents/*ollama* > "$LAB_DIR/phase1-install/ollama-launch-agent.txt" 2>/dev/null
ls -la /Library/LaunchDaemons/*ollama* > "$LAB_DIR/phase1-install/ollama-launch-daemon.txt" 2>/dev/null
# Capture the plist contents if present
find ~/Library/LaunchAgents /Library/LaunchDaemons -name '*ollama*' \
  -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase1-install/ollama-plist-contents.txt"

# Dedicated user/group check (Linux installer often creates an 'ollama' system user)
id ollama > "$LAB_DIR/phase1-install/ollama-user-check.txt" 2>&1
grep ollama /etc/passwd >> "$LAB_DIR/phase1-install/ollama-user-check.txt" 2>/dev/null
grep ollama /etc/group >> "$LAB_DIR/phase1-install/ollama-user-check.txt" 2>/dev/null

# Shell profile diff (did install modify PATH in dotfiles?)
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase1-install/shellprofile-diff-$base.txt" 2>&1
  fi
done

# Crontab diff
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

## Phase 2: First Launch — Daemon Start, Model Pull, and Idle State

**Purpose:** Capture what happens when the Ollama daemon starts and a model is pulled — process lineage, network connections for model download, localhost API listener, and config/state file creation.

> **Key difference from Class C tools:** Ollama has no authentication flow. There is no login, no OAuth, no API key prompt. The daemon starts and immediately begins listening on localhost:11434. The critical network event here is the **model pull** — a large, distinctive download from `registry.ollama.ai`.

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
script -q "$LAB_DIR/phase2-launch/terminal-session.log"
```

> You are now inside `script`. Everything typed and displayed is recorded.

### Start the Ollama Daemon

If the daemon is not already running (installer may auto-start it):

```bash
# Check if already running
ollama list 2>&1 | tee "$LAB_DIR/phase2-launch/pre-start-check.txt"

# If not running, start manually:
ollama serve &
OLLAMA_PID=$!
echo "Ollama daemon PID: $OLLAMA_PID" > "$LAB_DIR/phase2-launch/daemon-pid.txt"

# Give the daemon a few seconds to initialize
sleep 3
```

### Capture Daemon Startup State

```bash
# Process tree of the ollama daemon
pstree -p $(pgrep -f 'ollama serve' | head -1) > "$LAB_DIR/phase2-launch/ollama-process-tree.txt" 2>/dev/null

# Full process details
ps auxww | grep -E 'ollama' | grep -v grep > "$LAB_DIR/phase2-launch/ollama-processes.txt"

# Confirm localhost listener on port 11434
lsof -i :11434 > "$LAB_DIR/phase2-launch/port-11434-at-launch.txt" 2>&1
ss -tlnp | grep 11434 >> "$LAB_DIR/phase2-launch/port-11434-at-launch.txt" 2>/dev/null

# All listening ports (diff against baseline)
ss -tlnp > "$LAB_DIR/phase2-launch/listening-ports-at-launch.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/phase2-launch/listening-ports-at-launch.txt"

# Outbound connections
ss -tnp > "$LAB_DIR/phase2-launch/outbound-at-launch.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/phase2-launch/outbound-at-launch.txt"

# Ollama data directory contents at startup
ls -laR ~/.ollama > "$LAB_DIR/phase2-launch/ollama-dir-at-launch.txt" 2>&1

# API health check — verify daemon is responsive
curl -s http://localhost:11434/ > "$LAB_DIR/phase2-launch/api-health-check.txt" 2>&1
curl -s http://localhost:11434/api/tags > "$LAB_DIR/phase2-launch/api-tags-pre-pull.txt" 2>&1
```

### Pull a Model

This is a key IOC event — outbound traffic to `registry.ollama.ai` with large data transfer:

```bash
# Pull a small model to minimize lab time while still capturing the full signal
ollama pull tinyllama 2>&1 | tee "$LAB_DIR/phase2-launch/model-pull-output.txt"
echo "Pull exit code: $?" >> "$LAB_DIR/phase2-launch/model-pull-output.txt"
```

### Post-Pull Capture

```bash
# Model inventory via API
curl -s http://localhost:11434/api/tags | \
  python3 -m json.tool > "$LAB_DIR/phase2-launch/api-tags-post-pull.txt" 2>&1

# Model inventory via CLI
ollama list > "$LAB_DIR/phase2-launch/ollama-list-post-pull.txt" 2>&1

# Model storage directory — key File-layer IOC
ls -laR ~/.ollama/models/ > "$LAB_DIR/phase2-launch/model-storage.txt" 2>&1

# Manifest and blob inspection
find ~/.ollama/models -type f -name 'manifest' -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase2-launch/model-manifests.txt"

# Disk usage of model storage
du -sh ~/.ollama/ > "$LAB_DIR/phase2-launch/ollama-disk-usage.txt" 2>&1
du -sh ~/.ollama/models/ >> "$LAB_DIR/phase2-launch/ollama-disk-usage.txt" 2>&1

# New files created during launch and pull
find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -not -path '*/ollama-lab/*' \
  2>/dev/null > "$LAB_DIR/phase2-launch/new-files-at-launch.txt"

# Full data directory contents
ls -laR ~/.ollama > "$LAB_DIR/phase2-launch/ollama-dir-post-pull.txt" 2>&1

# Environment variable check — Ollama-specific vars that may affect behavior
env | grep -iE 'ollama|OLLAMA' > "$LAB_DIR/phase2-launch/ollama-env-runtime.txt" 2>/dev/null
echo "Exit code: $? (1 = no OLLAMA vars, typical for default config)" \
  >> "$LAB_DIR/phase2-launch/ollama-env-runtime.txt"

# strace on ollama daemon (Linux only, requires separate terminal with sudo)
# NOTE: The ollama daemon is a Go binary. strace on Go processes is less noisy
# than Node.js but still produces substantial output. Limit to 10 seconds.
sudo strace -p $(pgrep -f 'ollama' | head -1) -e trace=openat,connect \
  -f -o "$LAB_DIR/phase2-launch/strace-launch.txt" &
STRACE_PID=$!
sleep 10 && sudo kill $STRACE_PID 2>/dev/null
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

## Phase 3: Inference Session — Trigger Class B Behavioral Signals

**Purpose:** Validate the local model runtime IOCs. Exercise Ollama through CLI interactive inference, API-driven inference, and model management — the behavioral signatures that distinguish Class B tools from passive installations.

> **Key difference from Class C agentic sessions:** Ollama does not autonomously read files, write code, or execute shell commands. The behavioral signals here are about **repeated prompt/inference cycles**, **local API traffic patterns**, and **model management activity** — not autonomous execution loops. If Ollama is being driven by an external automation script (e.g., a bash loop calling the API), that script-to-API chain is itself a behavioral signal.

### Start Background Monitors

```bash
# Terminal A: Full traffic capture (includes localhost API traffic)
sudo tcpdump -i any -w "$LAB_DIR/phase3-inference/inference-traffic.pcap" &
TCPDUMP_PID=$!

# Terminal B: Process tree every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-inference/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase3-inference/pstree-stream.txt" 2>/dev/null || \
    ps auxf >> "$LAB_DIR/phase3-inference/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!

# Terminal C: Connection snapshots every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-inference/connections-stream.txt"
  ss -tnp >> "$LAB_DIR/phase3-inference/connections-stream.txt" 2>/dev/null || \
    lsof -i -nP >> "$LAB_DIR/phase3-inference/connections-stream.txt"
  sleep 2
done &
CONN_PID=$!

# Terminal D: Monitor port 11434 traffic specifically
sudo tcpdump -i lo port 11434 -l 2>/dev/null | \
  tee "$LAB_DIR/phase3-inference/localhost-api-traffic.txt" &
LO_PID=$!

# Terminal E: strace on ollama daemon (Linux only)
sudo strace -p $(pgrep -f 'ollama' | head -1) -e trace=openat,read,write,connect \
  -f -o "$LAB_DIR/phase3-inference/strace-inference.txt" &
STRACE_PID=$!
```

### Start Terminal Session Recorder (if not already running from Phase 2)

```bash
script -q "$LAB_DIR/phase3-inference/terminal-session.log"
```

### Task 3A: Interactive CLI Inference

```bash
# Run a simple interactive prompt via CLI
# This validates: CLI invocation IOC, prompt/inference cycle, process lineage
ollama run tinyllama "What is the capital of France? Answer in one sentence."
```

**While the inference runs, observe and note:**

1. **Process tree** — Does `ollama run` spawn as a separate process or communicate with the daemon? Watch for: `ollama` → model loading child processes.
2. **Localhost traffic** — Port 11434 should show request/response activity.
3. **Memory/GPU usage** — Model loading is a distinct resource spike.
4. **Response timing** — Note latency between prompt and first token (inference performance baseline).

### Task 3B: API-Driven Inference

```bash
# Simulate programmatic access via the local API
# This validates: localhost API traffic IOC, burst cadence

# Single prompt
curl -s http://localhost:11434/api/generate \
  -d '{"model": "tinyllama", "prompt": "Explain gravity in one sentence.", "stream": false}' \
  > "$LAB_DIR/phase3-inference/api-single-response.json" 2>&1

# Rapid burst of API calls (simulates automation/scripting pattern)
for i in $(seq 1 5); do
  echo "=== Request $i at $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3-inference/api-burst-responses.json"
  curl -s http://localhost:11434/api/generate \
    -d "{\"model\": \"tinyllama\", \"prompt\": \"Count to $i.\", \"stream\": false}" \
    >> "$LAB_DIR/phase3-inference/api-burst-responses.json" 2>&1
  echo "" >> "$LAB_DIR/phase3-inference/api-burst-responses.json"
done
```

### Task 3C: Model Management Activity

```bash
# Pull a second model to observe model-switching and storage growth
ollama pull phi 2>&1 | tee "$LAB_DIR/phase3-inference/second-model-pull.txt"

# List models (before and after)
ollama list > "$LAB_DIR/phase3-inference/model-list-post-second.txt" 2>&1

# Run inference on the second model
ollama run phi "Say hello." 2>&1 | tee "$LAB_DIR/phase3-inference/second-model-inference.txt"

# Model info inspection
ollama show tinyllama > "$LAB_DIR/phase3-inference/model-info-tinyllama.txt" 2>&1
ollama show phi > "$LAB_DIR/phase3-inference/model-info-phi.txt" 2>&1
```

### Task 3D: Scripted Automation Pattern (Optional — Higher-Risk Signal)

This simulates an automation script driving Ollama against local files — a pattern that bridges Class B toward higher-risk usage:

```bash
# Create a test workspace
mkdir -p ~/ollama-lab-workspace && cd ~/ollama-lab-workspace

# Create a sample file for the model to "analyze"
echo "def calculate_total(items): return sum(item.price for item in items)" \
  > ~/ollama-lab-workspace/sample.py

# Script that reads a local file and sends it to Ollama for analysis
CODE=$(cat ~/ollama-lab-workspace/sample.py)
curl -s http://localhost:11434/api/generate \
  -d "{\"model\": \"tinyllama\", \"prompt\": \"Review this code: $CODE\", \"stream\": false}" \
  > "$LAB_DIR/phase3-inference/scripted-analysis-response.json" 2>&1
```

### Post-Inference Capture

```bash
# Model storage growth
ls -laR ~/.ollama/models/ > "$LAB_DIR/phase3-inference/model-storage-post.txt" 2>&1
du -sh ~/.ollama/ > "$LAB_DIR/phase3-inference/ollama-disk-usage-post.txt" 2>&1
du -sh ~/.ollama/models/ >> "$LAB_DIR/phase3-inference/ollama-disk-usage-post.txt" 2>&1

# Diff model storage against Phase 2
diff "$LAB_DIR/phase2-launch/model-storage.txt" \
  "$LAB_DIR/phase3-inference/model-storage-post.txt" \
  > "$LAB_DIR/phase3-inference/model-storage-diff.txt" 2>&1

# Full data directory state
ls -laR ~/.ollama > "$LAB_DIR/phase3-inference/ollama-dir-post-inference.txt" 2>&1
diff "$LAB_DIR/phase2-launch/ollama-dir-post-pull.txt" \
  "$LAB_DIR/phase3-inference/ollama-dir-post-inference.txt" \
  > "$LAB_DIR/phase3-inference/ollama-dir-diff.txt" 2>&1

# Files changed across all of home since Phase 2
find ~ -newer "$LAB_DIR/phase2-launch/TIMESTAMP_MARKER" \
  -not -path '*/ollama-lab/*' \
  2>/dev/null > "$LAB_DIR/phase3-inference/new-files-during-inference.txt"

# Daemon resource usage snapshot
ps -p $(pgrep -f 'ollama' | head -1) -o pid,ppid,rss,vsz,%mem,%cpu,etime,comm \
  > "$LAB_DIR/phase3-inference/daemon-resource-usage.txt" 2>&1

# Log file capture (if any)
find ~/.ollama -name '*.log' -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase3-inference/ollama-logs.txt"

# Workspace contents (if Task 3D was performed)
if [ -d ~/ollama-lab-workspace ]; then
  find ~/ollama-lab-workspace -type f -ls > "$LAB_DIR/phase3-inference/workspace-files.txt"
fi
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID $LO_PID 2>/dev/null
sudo kill $TCPDUMP_PID $STRACE_PID 2>/dev/null
```

### Phase 3 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3-inference/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3-inference/phase3-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3-inference/"* > "$LAB_DIR/phase3-inference/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Session End — What Persists After Exit

**Purpose:** Determine what survives after the Ollama session ends. Unlike Class C tools with no persistence, Ollama is expected to have **active persistence** — the daemon may continue running via systemd/launchd, and model storage persists. This is a defining Class B characteristic.

### Stop the Ollama Daemon

```bash
# Graceful stop
ollama stop 2>&1 | tee "$LAB_DIR/phase4-teardown/daemon-stop-output.txt"

# If manually started, kill the process
kill $OLLAMA_PID 2>/dev/null

# If running as a system service:
# Linux:
sudo systemctl stop ollama 2>/dev/null
# macOS:
launchctl unload ~/Library/LaunchAgents/com.ollama.ollama.plist 2>/dev/null
```

Exit the `script` session with `exit`.

### Wait and Capture

Allow 10 seconds for cleanup, then:

```bash
# Process check: is the daemon still running?
ps auxww | grep -E 'ollama' | grep -v grep > "$LAB_DIR/phase4-teardown/remaining-processes.txt"
echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt")" \
  >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"

# Orphan child processes?
pstree -p > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null || \
  ps auxf > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt"

# Is port 11434 still in use?
lsof -i :11434 > "$LAB_DIR/phase4-teardown/port-11434-post-exit.txt" 2>&1
echo "Exit code: $? (1 = port released, expected)" >> "$LAB_DIR/phase4-teardown/port-11434-post-exit.txt"

# Lingering network connections
ss -tnp > "$LAB_DIR/phase4-teardown/connections-post-exit.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/phase4-teardown/connections-post-exit.txt"
diff "$LAB_DIR/baseline/active-connections.txt" \
  "$LAB_DIR/phase4-teardown/connections-post-exit.txt" \
  > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1

# Listening ports
ss -tlnp > "$LAB_DIR/phase4-teardown/listening-ports-post.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/phase4-teardown/listening-ports-post.txt"

# Persistent files and model storage — THIS IS THE KEY CLASS B SIGNAL
# Models should persist across daemon restarts
ls -laR ~/.ollama > "$LAB_DIR/phase4-teardown/ollama-dir-final.txt" 2>&1
du -sh ~/.ollama/ > "$LAB_DIR/phase4-teardown/ollama-disk-final.txt" 2>&1
du -sh ~/.ollama/models/ >> "$LAB_DIR/phase4-teardown/ollama-disk-final.txt" 2>&1

# Full diff: what files exist now that didn't at baseline?
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt"

# Model storage artifact detail
find ~/.ollama -type f -exec ls -la {} \; 2>/dev/null > "$LAB_DIR/phase4-teardown/ollama-artifacts-detail.txt"
find ~/.ollama -type f -exec file {} \; 2>/dev/null >> "$LAB_DIR/phase4-teardown/ollama-artifacts-detail.txt"

# Shell profile modifications
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase4-teardown/shellprofile-diff-$base.txt" 2>&1
  fi
done

# Persistence mechanisms — key diff against baseline
crontab -l > "$LAB_DIR/phase4-teardown/crontab-final.txt" 2>&1
diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase4-teardown/crontab-final.txt" \
  > "$LAB_DIR/phase4-teardown/crontab-diff.txt" 2>&1

# Linux: systemd service state after stop
systemctl status ollama > "$LAB_DIR/phase4-teardown/ollama-service-status.txt" 2>/dev/null
systemctl is-enabled ollama > "$LAB_DIR/phase4-teardown/ollama-service-enabled.txt" 2>/dev/null
systemctl --user list-units --type=service > "$LAB_DIR/phase4-teardown/user-services-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/user-services.txt" "$LAB_DIR/phase4-teardown/user-services-final.txt" \
  > "$LAB_DIR/phase4-teardown/services-diff.txt" 2>&1

# macOS: LaunchAgent/Daemon state
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" "$LAB_DIR/phase4-teardown/launch-agents-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1
ls -la /Library/LaunchDaemons/ > "$LAB_DIR/phase4-teardown/launch-daemons-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-daemons.txt" "$LAB_DIR/phase4-teardown/launch-daemons-final.txt" \
  > "$LAB_DIR/phase4-teardown/launch-daemons-diff.txt" 2>&1

# Dedicated user/group persistence (Linux)
id ollama > "$LAB_DIR/phase4-teardown/ollama-user-final.txt" 2>&1

# Verify daemon auto-restart behavior (does it come back after stop?)
sleep 5
ps auxww | grep -E 'ollama' | grep -v grep > "$LAB_DIR/phase4-teardown/auto-restart-check.txt"
echo "Processes found after 5s wait: $(wc -l < "$LAB_DIR/phase4-teardown/auto-restart-check.txt")" \
  >> "$LAB_DIR/phase4-teardown/auto-restart-check.txt"
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

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.4:

| Layer | IOC (from Section 4.4) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | `ollama` daemon/service process running on host | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | CLI invocations: `ollama run`, `ollama pull`, `ollama serve` | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Parent-child lineage from terminal/scripts to ollama calls | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Model storage: `~/.ollama/models/` directory with manifests | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Pulled model metadata, version/tag files, pull timestamps | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Cache/artifact growth patterns indicating active inference | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Localhost API traffic (default `:11434`) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Outbound model pull traffic to `registry.ollama.ai` | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | OS user/session tied to daemon and CLI interactions | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Repeated prompt/inference cycles via local API/CLI | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Automation scripts invoking local generation against repos/data | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Unsanctioned model pulls and rapid model switching | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

### 5.2 Confidence Score Calculation

Using Appendix B formula with Ollama signal weights:

```
Layer Weights (five-layer defaults from Appendix B):
  Process:  0.30
  File:     0.20
  Network:  0.15
  Identity: 0.15
  Behavior: 0.20
```

> **Note:** Unlike Claude Code (INIT-43), Ollama does not yet have tool-specific calibrated weights. This lab run should produce the empirical data to derive them. Expect network (localhost + registry) and file (model storage) layers to carry more weight for Class B tools than they do for Class C.

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
  [ ] Custom port (non-default 11434):             −0.05 (proposed, Ollama-specific)

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
Run ID:              LAB-RUN-003
Date:                [execution date]
Tool:                Ollama [version from ollama --version]
Scenario ID:         OL-POS-01 (Standard install + model pull + inference session)
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

### 5.4 Class B-Specific Analysis

Document these Class B characterization questions:

| Question | Finding |
|---|---|
| Does the installer register a persistent daemon (systemd/launchd)? | |
| Does the daemon auto-restart after being stopped? | |
| Does model storage persist across daemon restarts? | |
| What is the disk footprint after pulling two models? | |
| Is the localhost API listener authenticated or open? | |
| Can the API be reached from non-localhost addresses? | |
| Does the installer create a dedicated system user? | |
| Are there any outbound connections beyond `registry.ollama.ai`? | |

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
LAB-RUN-003/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── ollama-dir-check.txt
│   ├── ollama-artifact-scan.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── ollama-process-check.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── port-11434-check.txt
│   ├── env-vars.txt
│   ├── ollama-env.txt
│   ├── which-ollama.txt
│   ├── ollama-service-check.txt
│   ├── user-services.txt
│   ├── crontab.txt
│   ├── launch-agents.txt
│   ├── launch-daemons.txt
│   ├── ollama-plist-check.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── install-output.txt               ← full install log
│   ├── ollama-version.txt               ← explicit version
│   ├── install-traffic.pcap             ← network capture
│   ├── dns-queries.txt
│   ├── ps-stream.txt
│   ├── which-ollama.txt
│   ├── binary-metadata.txt              ← hash, path, type
│   ├── new-files.txt
│   ├── ollama-dir-post.txt
│   ├── ollama-systemd-check.txt         ← Linux service registration
│   ├── ollama-service-unit.txt          ← systemd unit file contents
│   ├── ollama-systemd-files.txt
│   ├── ollama-launch-agent.txt          ← macOS LaunchAgent
│   ├── ollama-launch-daemon.txt         ← macOS LaunchDaemon
│   ├── ollama-plist-contents.txt        ← plist file contents
│   ├── ollama-user-check.txt            ← dedicated system user
│   ├── shellprofile-diff-*.txt
│   ├── crontab-post.txt
│   └── crontab-diff.txt
├── phase2-launch/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── terminal-session.log             ← full TTY recording
│   ├── launch-traffic.pcap
│   ├── connections-stream.txt
│   ├── pstree-stream.txt
│   ├── pre-start-check.txt
│   ├── daemon-pid.txt
│   ├── ollama-process-tree.txt
│   ├── ollama-processes.txt
│   ├── port-11434-at-launch.txt         ← localhost listener confirmation
│   ├── listening-ports-at-launch.txt
│   ├── outbound-at-launch.txt
│   ├── ollama-dir-at-launch.txt
│   ├── api-health-check.txt             ← API responsiveness
│   ├── api-tags-pre-pull.txt
│   ├── model-pull-output.txt            ← model pull log
│   ├── api-tags-post-pull.txt
│   ├── ollama-list-post-pull.txt
│   ├── model-storage.txt                ← model directory listing
│   ├── model-manifests.txt              ← manifest file contents
│   ├── ollama-disk-usage.txt
│   ├── new-files-at-launch.txt
│   ├── ollama-dir-post-pull.txt
│   ├── ollama-env-runtime.txt
│   └── strace-launch.txt               ← syscall trace (Linux)
├── phase3-inference/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── terminal-session.log             ← inference session recording
│   ├── inference-traffic.pcap
│   ├── pstree-stream.txt
│   ├── connections-stream.txt
│   ├── localhost-api-traffic.txt        ← port 11434 traffic capture
│   ├── strace-inference.txt             ← syscall trace (Linux)
│   ├── api-single-response.json         ← single API inference
│   ├── api-burst-responses.json         ← burst API pattern
│   ├── second-model-pull.txt            ← model switching
│   ├── model-list-post-second.txt
│   ├── second-model-inference.txt
│   ├── model-info-tinyllama.txt
│   ├── model-info-phi.txt
│   ├── scripted-analysis-response.json  ← automation pattern (if Task 3D run)
│   ├── model-storage-post.txt
│   ├── ollama-disk-usage-post.txt
│   ├── model-storage-diff.txt
│   ├── ollama-dir-post-inference.txt
│   ├── ollama-dir-diff.txt
│   ├── new-files-during-inference.txt
│   ├── daemon-resource-usage.txt
│   ├── ollama-logs.txt
│   └── workspace-files.txt             ← (if Task 3D run)
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── daemon-stop-output.txt
│   ├── remaining-processes.txt
│   ├── pstree-post-exit.txt
│   ├── port-11434-post-exit.txt         ← port release check
│   ├── connections-post-exit.txt
│   ├── connections-diff.txt
│   ├── listening-ports-post.txt
│   ├── ollama-dir-final.txt             ← persistent model storage
│   ├── ollama-disk-final.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── ollama-artifacts-detail.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── ollama-service-status.txt        ← systemd state post-stop
│   ├── ollama-service-enabled.txt       ← auto-start persistence
│   ├── user-services-final.txt
│   ├── services-diff.txt
│   ├── launch-agents-final.txt
│   ├── launch-agents-diff.txt
│   ├── launch-daemons-final.txt
│   ├── launch-daemons-diff.txt
│   ├── ollama-user-final.txt            ← dedicated user persistence
│   └── auto-restart-check.txt           ← daemon respawn behavior
└── [Phase 5 analysis filled in manually or in a separate doc]
```

---

## Post-Run: Next Steps

1. **Complete the Section 5 analysis** — fill in every cell of the observation matrix, the Class B characterization table, and calculate the confidence score.
2. **Derive Ollama-specific layer weights** — use observed signal strengths to propose calibrated weights for Class B tools (compare against Appendix B defaults).
3. **Update the Playbook Lab Run Log** (Section 12.5) with results.
4. **File playbook feedback** for any IOCs in Section 4.4 that were predicted incorrectly or missing.
5. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
6. **Plan next run** — OL-POS-02 (local API automation session) or OL-EVA-01 (custom port + containerized evasion).
