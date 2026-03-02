# Lab Run Protocol: OpenClaw Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-007  
**Tool:** OpenClaw (`openclaw`)  
**Class:** C (Autonomous Executor) with persistent daemon characteristics (Class B overlay)  
**Playbook Reference:** Section 4.11 (IOCs), Section 12 (Lab Validation), Appendix B (Confidence Scoring)  
**Target Scenario:** Positive — Standard install, onboarding, agentic task execution, skill creation, proactive behavior assessment  
**Scenario ID:** OC-POS-01  
**Status:** `NOT STARTED`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | macOS 26.3, ARM64 (Apple Silicon M2) |
| **Node.js** | Node ≥22 with npm |
| **Shell** | zsh |
| **Root/sudo** | Required for `tcpdump` (optional — capture what we can without it) |
| **Disk** | Sufficient space for evidence artifacts and npm globals (~1 GB headroom) |
| **Network** | Outbound internet access (npm registry, model provider API) |
| **API Key** | `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in environment |

### Tool Availability Check

Run before starting. All must be present:

```bash
node --version          # ≥22 required
npm --version
which pstree           # process tree viewer (brew install pstree)
which lsof             # port/connection inspection
which shasum           # evidence hashing
which script           # terminal session recorder
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/openclaw-lab/LAB-RUN-007
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-onboard,phase3a-basic,phase3b-agentic,phase3c-selfmod,phase3d-proactive,phase4-teardown}
```

### Safety: Dedicated Workspace

All OpenClaw tasks must be scoped to a dedicated workspace. Do NOT connect real email, calendar, or financial accounts.

```bash
mkdir -p ~/openclaw-lab-workspace
```

---

## Pre-Install: Baseline Capture

**Purpose:** Establish clean-state reference for every detection layer.

### File System Baseline

```bash
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"

ls -la ~/.openclaw 2>&1 > "$LAB_DIR/baseline/openclaw-dir-check.txt"
find ~ -name '*openclaw*' -o -name '*clawdbot*' -o -name '*moltbot*' 2>/dev/null \
  > "$LAB_DIR/baseline/openclaw-artifact-scan.txt"

ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"

for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename $f).bak"
done
```

### Process Baseline

```bash
ps auxww > "$LAB_DIR/baseline/ps-full.txt"
pstree -p > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null || ps auxf > "$LAB_DIR/baseline/ps-tree.txt"

ps auxww | grep -i openclaw | grep -v grep > "$LAB_DIR/baseline/openclaw-process-check.txt" 2>&1
echo "Matching processes: $(wc -l < "$LAB_DIR/baseline/openclaw-process-check.txt")" \
  >> "$LAB_DIR/baseline/openclaw-process-check.txt"
```

### Network Baseline

```bash
ss -tlnp > "$LAB_DIR/baseline/listening-ports.txt" 2>/dev/null || \
  lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"

ss -tnp > "$LAB_DIR/baseline/active-connections.txt" 2>/dev/null || \
  lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"

lsof -i :18789 > "$LAB_DIR/baseline/port-18789-check.txt" 2>&1
echo "Exit code: $? (1 = port not in use, expected)" >> "$LAB_DIR/baseline/port-18789-check.txt"
```

### Environment Baseline

```bash
env | sort > "$LAB_DIR/baseline/env-vars.txt"

env | grep -iE 'anthropic|openai|openclaw' > "$LAB_DIR/baseline/ai-env.txt" 2>/dev/null
echo "Exit code: $?" >> "$LAB_DIR/baseline/ai-env.txt"

npm list -g --depth=0 > "$LAB_DIR/baseline/npm-globals.txt" 2>&1

which openclaw > "$LAB_DIR/baseline/which-openclaw.txt" 2>&1
echo "Exit code: $? (1 = not found, expected)" >> "$LAB_DIR/baseline/which-openclaw.txt"
```

### Persistence Mechanism Baseline

```bash
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
find ~/Library/LaunchAgents -name '*openclaw*' -o -name '*clawdbot*' \
  2>/dev/null > "$LAB_DIR/baseline/openclaw-plist-check.txt"
echo "Exit code: $? (1 = none found, expected)" >> "$LAB_DIR/baseline/openclaw-plist-check.txt"
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

**Purpose:** Capture the full npm global installation footprint — files created, network connections made, binaries placed, postinstall scripts executed.

### Start Background Monitors

```bash
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase1-install/ps-stream.txt"
  ps auxww >> "$LAB_DIR/phase1-install/ps-stream.txt"
  sleep 2
done &
PS_PID=$!
```

### Run Installation

```bash
npm install -g openclaw@latest 2>&1 | \
  tee "$LAB_DIR/phase1-install/npm-install-output.txt"

echo "Install exit code: $?" >> "$LAB_DIR/phase1-install/npm-install-output.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID 2>/dev/null
```

### Post-Install Capture

```bash
npm list -g --depth=0 > "$LAB_DIR/phase1-install/npm-globals-post.txt" 2>&1
diff "$LAB_DIR/baseline/npm-globals.txt" "$LAB_DIR/phase1-install/npm-globals-post.txt" \
  > "$LAB_DIR/phase1-install/npm-globals-diff.txt"

which openclaw > "$LAB_DIR/phase1-install/which-openclaw.txt" 2>&1

OPENCLAW_BIN=$(which openclaw 2>/dev/null)
if [ -n "$OPENCLAW_BIN" ]; then
  ls -la "$OPENCLAW_BIN" > "$LAB_DIR/phase1-install/binary-metadata.txt"
  file "$OPENCLAW_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
  readlink -f "$OPENCLAW_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt" 2>/dev/null
  shasum -a 256 "$OPENCLAW_BIN" >> "$LAB_DIR/phase1-install/binary-metadata.txt"
fi

openclaw --version > "$LAB_DIR/phase1-install/openclaw-version.txt" 2>&1
npm list -g openclaw --json > "$LAB_DIR/phase1-install/openclaw-npm-info.json" 2>&1

ls -laR ~/.openclaw 2>&1 > "$LAB_DIR/phase1-install/openclaw-dir-post.txt"

find ~ -newer "$LAB_DIR/baseline/TIMESTAMP_MARKER" \
  -not -path '*/openclaw-lab/*' \
  -not -path '*/.cache/*' \
  -not -path '*/node_modules/*' \
  2>/dev/null > "$LAB_DIR/phase1-install/new-files.txt"

for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase1-install/shellprofile-diff-$base.txt" 2>&1
  fi
done

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

## Phase 2: Onboarding — Config Creation, Daemon Registration, and Gateway Start

**Purpose:** Capture the full onboarding flow — interactive setup, config file creation, daemon registration, gateway initialization, and initial network connections.

> **Key difference from other tools:** OpenClaw's onboarding wizard (`openclaw onboard`) creates the config directory, registers a daemon (LaunchAgent/systemd), configures the model provider, and starts the gateway. This is the most complex first-run behavior of any profiled tool.

### Start Background Monitors

```bash
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
  sleep 2
done &
CONN_PID=$!

while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase2-onboard/pstree-stream.txt" 2>/dev/null || \
    ps auxf >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!
```

### Run Onboarding

```bash
script -q "$LAB_DIR/phase2-onboard/terminal-session.log"
# Inside script session:
openclaw onboard --install-daemon
```

**During onboarding, note:**
1. What questions does the wizard ask?
2. What model provider options are presented?
3. Does it create files during each wizard step?
4. Does it register a LaunchAgent?
5. Does it start the gateway automatically?

### Post-Onboard Capture

```bash
ls -laR ~/.openclaw > "$LAB_DIR/phase2-onboard/openclaw-dir-at-onboard.txt" 2>&1

# Config file contents (HIGH VALUE — contains model provider, channels, etc.)
cat ~/.openclaw/openclaw.json > "$LAB_DIR/phase2-onboard/openclaw-config.txt" 2>&1

# Workspace contents
ls -laR ~/.openclaw/workspace > "$LAB_DIR/phase2-onboard/workspace-contents.txt" 2>&1

# Agent state
ls -laR ~/.openclaw/agents > "$LAB_DIR/phase2-onboard/agents-state.txt" 2>&1

# Credentials directory
ls -laR ~/.openclaw/credentials > "$LAB_DIR/phase2-onboard/credentials-dir.txt" 2>&1

# LaunchAgent registration — KEY PERSISTENCE SIGNAL
ls -la ~/Library/LaunchAgents/*openclaw* > "$LAB_DIR/phase2-onboard/openclaw-launch-agent.txt" 2>/dev/null
find ~/Library/LaunchAgents -name '*openclaw*' -o -name '*clawdbot*' \
  -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase2-onboard/openclaw-plist-contents.txt"

# Gateway status
openclaw status > "$LAB_DIR/phase2-onboard/openclaw-status.txt" 2>&1

# Process tree of gateway
ps auxww | grep -E 'openclaw|gateway' | grep -v grep > "$LAB_DIR/phase2-onboard/openclaw-processes.txt"
pstree -p $(pgrep -f 'openclaw' | head -1) > "$LAB_DIR/phase2-onboard/openclaw-process-tree.txt" 2>/dev/null

# Port 18789 listener — KEY NETWORK SIGNAL
lsof -i :18789 > "$LAB_DIR/phase2-onboard/port-18789-at-onboard.txt" 2>&1

# All listening ports (diff against baseline)
lsof -i -nP | grep LISTEN > "$LAB_DIR/phase2-onboard/listening-ports-at-onboard.txt"

# Outbound connections
lsof -i -nP > "$LAB_DIR/phase2-onboard/outbound-at-onboard.txt"

# New files since Phase 1
find ~ -newer "$LAB_DIR/phase1-install/TIMESTAMP_MARKER" \
  -not -path '*/openclaw-lab/*' \
  2>/dev/null > "$LAB_DIR/phase2-onboard/new-files-at-onboard.txt"

# Prompt injection files in workspace
for f in AGENTS.md SOUL.md TOOLS.md; do
  if [ -f ~/.openclaw/workspace/$f ]; then
    echo "=== $f ===" >> "$LAB_DIR/phase2-onboard/workspace-prompt-files.txt"
    cat ~/.openclaw/workspace/$f >> "$LAB_DIR/phase2-onboard/workspace-prompt-files.txt"
    echo "" >> "$LAB_DIR/phase2-onboard/workspace-prompt-files.txt"
  fi
done
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Phase 2 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase2-onboard/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-onboard/phase2-end-time.txt"
shasum -a 256 "$LAB_DIR/phase2-onboard/"* > "$LAB_DIR/phase2-onboard/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3A: Basic Interaction — CLI Agent Message

**Purpose:** Validate basic agentic interaction via CLI. Send a simple task and capture process tree, network activity, and file changes.

### Start Background Monitors

```bash
while true; do
  echo "=== $(date -u +%H:%M:%S.%N) ===" >> "$LAB_DIR/phase3a-basic/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase3a-basic/pstree-stream.txt" 2>/dev/null
  sleep 1
done &
PS_PID=$!

while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3a-basic/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase3a-basic/connections-stream.txt"
  sleep 1
done &
CONN_PID=$!
```

### Send Basic Task

```bash
openclaw agent --message "What is the capital of France? Answer in one sentence." \
  2>&1 | tee "$LAB_DIR/phase3a-basic/basic-interaction-output.txt"
```

### Post-Task Capture

```bash
ps auxww | grep -E 'openclaw|node.*gateway' | grep -v grep > "$LAB_DIR/phase3a-basic/openclaw-processes.txt"
lsof -i :18789 > "$LAB_DIR/phase3a-basic/port-18789-during-task.txt" 2>&1
lsof -i -nP > "$LAB_DIR/phase3a-basic/outbound-during-task.txt"

ls -laR ~/.openclaw/agents > "$LAB_DIR/phase3a-basic/agents-state-post.txt" 2>&1
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID 2>/dev/null
```

### Phase 3A Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3a-basic/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3a-basic/phase3a-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3a-basic/"* > "$LAB_DIR/phase3a-basic/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3B: Agentic Execution — Shell Commands and File Creation

**Purpose:** Validate Class C behavioral IOCs — shell execution, file creation, and the agentic loop. Give OpenClaw a task that requires creating files and running commands.

### Start Background Monitors (1-second resolution for agentic bursts)

```bash
while true; do
  echo "=== $(date -u +%H:%M:%S.%N) ===" >> "$LAB_DIR/phase3b-agentic/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase3b-agentic/pstree-stream.txt" 2>/dev/null
  sleep 1
done &
PS_PID=$!

while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3b-agentic/connections-stream.txt"
  lsof -i -nP >> "$LAB_DIR/phase3b-agentic/connections-stream.txt"
  sleep 1
done &
CONN_PID=$!

fswatch ~/openclaw-lab-workspace > "$LAB_DIR/phase3b-agentic/file-events.txt" 2>/dev/null &
FSWATCH_PID=$!
```

### Issue Agentic Task

```bash
cd ~/openclaw-lab-workspace

openclaw agent --message "Create a simple Python hello world project in ~/openclaw-lab-workspace with a README and a test file, then run the test." \
  2>&1 | tee "$LAB_DIR/phase3b-agentic/agentic-task-output.txt"
```

### Post-Task Capture

```bash
find ~/openclaw-lab-workspace -type f -ls > "$LAB_DIR/phase3b-agentic/workspace-files.txt"

for f in $(find ~/openclaw-lab-workspace -type f -not -path '*/__pycache__/*'); do
  echo "=== $f ===" >> "$LAB_DIR/phase3b-agentic/workspace-contents.txt"
  cat "$f" >> "$LAB_DIR/phase3b-agentic/workspace-contents.txt"
  echo "" >> "$LAB_DIR/phase3b-agentic/workspace-contents.txt"
done

ls -laR ~/.openclaw/agents > "$LAB_DIR/phase3b-agentic/agents-state-post-agentic.txt" 2>&1

find ~ -newer "$LAB_DIR/phase3a-basic/TIMESTAMP_MARKER" \
  -not -path '*/openclaw-lab/*' \
  2>/dev/null > "$LAB_DIR/phase3b-agentic/new-files-during-agentic.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $CONN_PID $FSWATCH_PID 2>/dev/null
```

### Phase 3B Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3b-agentic/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3b-agentic/phase3b-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3b-agentic/"* > "$LAB_DIR/phase3b-agentic/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3C: Self-Modification — Skill Authoring and Hot-Reload

**Purpose:** Validate the highest-risk behavioral pattern — the agent writing its own skills/plugins. Ask OpenClaw to create a new skill and verify it is hot-reloaded.

### Start Background Monitors

```bash
while true; do
  echo "=== $(date -u +%H:%M:%S.%N) ===" >> "$LAB_DIR/phase3c-selfmod/pstree-stream.txt"
  pstree -p >> "$LAB_DIR/phase3c-selfmod/pstree-stream.txt" 2>/dev/null
  sleep 1
done &
PS_PID=$!

fswatch ~/.openclaw/workspace/skills > "$LAB_DIR/phase3c-selfmod/skill-file-events.txt" 2>/dev/null &
FSWATCH_PID=$!
```

### Pre-Skill Snapshot

```bash
ls -laR ~/.openclaw/workspace/skills > "$LAB_DIR/phase3c-selfmod/skills-before.txt" 2>&1
```

### Request Skill Creation

```bash
openclaw agent --message "Create a new skill for yourself that can convert temperatures between Celsius and Fahrenheit. Write it as a SKILL.md file in your skills directory." \
  2>&1 | tee "$LAB_DIR/phase3c-selfmod/skill-creation-output.txt"
```

### Post-Skill Capture

```bash
ls -laR ~/.openclaw/workspace/skills > "$LAB_DIR/phase3c-selfmod/skills-after.txt" 2>&1
diff "$LAB_DIR/phase3c-selfmod/skills-before.txt" "$LAB_DIR/phase3c-selfmod/skills-after.txt" \
  > "$LAB_DIR/phase3c-selfmod/skills-diff.txt" 2>&1

find ~/.openclaw/workspace/skills -type f -exec echo "=== {} ===" \; -exec cat {} \; \
  2>/dev/null > "$LAB_DIR/phase3c-selfmod/skill-contents.txt"
```

### Stop Background Monitors

```bash
kill $PS_PID $FSWATCH_PID 2>/dev/null
```

### Phase 3C Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3c-selfmod/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3c-selfmod/phase3c-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3c-selfmod/"* > "$LAB_DIR/phase3c-selfmod/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 3D: Proactive/Scheduled Behavior (Architecture Assessment)

**Purpose:** Assess the cron/heartbeat/webhook infrastructure for proactive agent execution. If configurable in lab timeframe, capture an autonomous agent turn triggered by schedule rather than user input.

> **Note:** Full proactive behavior testing may require extended observation time. If cron configuration is not feasible in lab, document the architectural capability and flag for future testing.

### Cron Architecture Assessment

```bash
openclaw agent --message "List all available cron and scheduling capabilities you have. What types of scheduled tasks can you create?" \
  2>&1 | tee "$LAB_DIR/phase3d-proactive/cron-capabilities.txt"

cat ~/.openclaw/openclaw.json | python3 -m json.tool > "$LAB_DIR/phase3d-proactive/config-state.txt" 2>&1
```

### Phase 3D Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3d-proactive/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase3d-proactive/phase3d-end-time.txt"
shasum -a 256 "$LAB_DIR/phase3d-proactive/"* > "$LAB_DIR/phase3d-proactive/EVIDENCE-HASHES.txt" 2>/dev/null
```

---

## Phase 4: Teardown — What Persists After Exit

**Purpose:** Determine what survives after OpenClaw is stopped. OpenClaw has the strongest expected persistence of any profiled tool — daemon, config, credentials, session history, skills, LaunchAgent.

### Stop OpenClaw

```bash
openclaw stop 2>&1 | tee "$LAB_DIR/phase4-teardown/daemon-stop-output.txt"
sleep 10
```

### Post-Stop Capture

```bash
ps auxww | grep -E 'openclaw|gateway' | grep -v grep > "$LAB_DIR/phase4-teardown/remaining-processes.txt"
echo "Matching processes: $(wc -l < "$LAB_DIR/phase4-teardown/remaining-processes.txt")" \
  >> "$LAB_DIR/phase4-teardown/remaining-processes.txt"

pstree -p > "$LAB_DIR/phase4-teardown/pstree-post-exit.txt" 2>/dev/null

lsof -i :18789 > "$LAB_DIR/phase4-teardown/port-18789-post-exit.txt" 2>&1
echo "Exit code: $? (1 = port released)" >> "$LAB_DIR/phase4-teardown/port-18789-post-exit.txt"

lsof -i -nP > "$LAB_DIR/phase4-teardown/connections-post-exit.txt"
diff "$LAB_DIR/baseline/active-connections.txt" \
  "$LAB_DIR/phase4-teardown/connections-post-exit.txt" \
  > "$LAB_DIR/phase4-teardown/connections-diff.txt" 2>&1

lsof -i -nP | grep LISTEN > "$LAB_DIR/phase4-teardown/listening-ports-post.txt"

# Persistent state — KEY: what survives stop?
ls -laR ~/.openclaw > "$LAB_DIR/phase4-teardown/openclaw-dir-final.txt" 2>&1
du -sh ~/.openclaw/ > "$LAB_DIR/phase4-teardown/openclaw-disk-final.txt" 2>&1

find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' \
  2>/dev/null > "$LAB_DIR/phase4-teardown/home-tree-final.txt"
diff "$LAB_DIR/baseline/home-tree.txt" "$LAB_DIR/phase4-teardown/home-tree-final.txt" \
  > "$LAB_DIR/phase4-teardown/home-tree-diff.txt"

find ~/.openclaw -type f -exec ls -la {} \; 2>/dev/null > "$LAB_DIR/phase4-teardown/openclaw-artifacts-detail.txt"
find ~/.openclaw -type f -exec file {} \; 2>/dev/null >> "$LAB_DIR/phase4-teardown/openclaw-artifacts-detail.txt"

for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  base=$(basename "$f")
  if [ -f "$f" ] && [ -f "$LAB_DIR/baseline/$base.bak" ]; then
    diff "$LAB_DIR/baseline/$base.bak" "$f" > "$LAB_DIR/phase4-teardown/shellprofile-diff-$base.txt" 2>&1
  fi
done

crontab -l > "$LAB_DIR/phase4-teardown/crontab-final.txt" 2>&1
diff "$LAB_DIR/baseline/crontab.txt" "$LAB_DIR/phase4-teardown/crontab-final.txt" \
  > "$LAB_DIR/phase4-teardown/crontab-diff.txt" 2>&1

# LaunchAgent persistence — does it survive daemon stop?
ls -la ~/Library/LaunchAgents/*openclaw* > "$LAB_DIR/phase4-teardown/launch-agents-final.txt" 2>/dev/null
diff "$LAB_DIR/baseline/launch-agents.txt" \
  <(ls -la ~/Library/LaunchAgents/ 2>/dev/null) \
  > "$LAB_DIR/phase4-teardown/launch-agents-diff.txt" 2>&1

# Auto-restart check: does the daemon come back after stop?
sleep 5
ps auxww | grep -E 'openclaw|gateway' | grep -v grep > "$LAB_DIR/phase4-teardown/auto-restart-check.txt"
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

| Layer | IOC (from Section 4.11) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | `openclaw` CLI binary / gateway daemon process | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Child process chains: gateway → shell → commands | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Persistent daemon (LaunchAgent on macOS) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Cron/scheduled task execution | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `~/.openclaw/` global config/state directory | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `~/.openclaw/openclaw.json` central config | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Skills directory with self-authored skills | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Credentials directory | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Session/conversation persistence | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | LaunchAgent plist | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Workspace prompt files (AGENTS.md, SOUL.md, TOOLS.md) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Gateway WS listener on `:18789` | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Model provider API traffic | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Chat platform connections | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | Model provider API keys in config/env | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | Chat platform credentials in config | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | OS user running daemon | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Shell command execution from agent context | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Self-modification (skill authoring + hot-reload) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Rapid multi-file write during agentic task | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | Proactive/scheduled execution | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

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
Run ID:              LAB-RUN-007
Date:                [execution date]
Tool:                OpenClaw [version]
Scenario ID:         OC-POS-01 (Standard install + onboarding + agentic task + skill creation)
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

### 5.4 Cross-Class Comparison

| Question | Finding |
|---|---|
| How does the persistence posture compare to Ollama (Class B)? | |
| How does agentic execution compare to Claude Code / Open Interpreter (Class C)? | |
| Are chat platform connections observable without connecting accounts? | |
| Does the daemon auto-restart after stop? | |
| What is the disk footprint after onboarding + agentic task? | |
| Is the Gateway WebSocket authenticated or open? | |
| Does skill hot-reload work? Is the self-modification observable? | |
| What novel IOCs exist that aren't in any other profile? | |

### 5.5 Findings and Playbook Feedback

| Finding | Affected Section | Recommended Change |
|---|---|---|
| | | |
| | | |
| | | |

---

## Evidence Inventory Checklist

When complete, `$LAB_DIR` should contain:

```
LAB-RUN-007/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── openclaw-dir-check.txt
│   ├── openclaw-artifact-scan.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── openclaw-process-check.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── port-18789-check.txt
│   ├── env-vars.txt
│   ├── ai-env.txt
│   ├── npm-globals.txt
│   ├── which-openclaw.txt
│   ├── crontab.txt
│   ├── launch-agents.txt
│   ├── openclaw-plist-check.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── npm-install-output.txt
│   ├── openclaw-version.txt
│   ├── openclaw-npm-info.json
│   ├── ps-stream.txt
│   ├── npm-globals-post.txt
│   ├── npm-globals-diff.txt
│   ├── which-openclaw.txt
│   ├── binary-metadata.txt
│   ├── new-files.txt
│   ├── openclaw-dir-post.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-post.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-post.txt
│   └── launch-agents-diff.txt
├── phase2-onboard/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── terminal-session.log
│   ├── connections-stream.txt
│   ├── pstree-stream.txt
│   ├── openclaw-dir-at-onboard.txt
│   ├── openclaw-config.txt
│   ├── workspace-contents.txt
│   ├── agents-state.txt
│   ├── credentials-dir.txt
│   ├── openclaw-launch-agent.txt
│   ├── openclaw-plist-contents.txt
│   ├── openclaw-status.txt
│   ├── openclaw-processes.txt
│   ├── openclaw-process-tree.txt
│   ├── port-18789-at-onboard.txt
│   ├── listening-ports-at-onboard.txt
│   ├── outbound-at-onboard.txt
│   ├── new-files-at-onboard.txt
│   └── workspace-prompt-files.txt
├── phase3a-basic/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt
│   ├── connections-stream.txt
│   ├── basic-interaction-output.txt
│   ├── openclaw-processes.txt
│   ├── port-18789-during-task.txt
│   ├── outbound-during-task.txt
│   └── agents-state-post.txt
├── phase3b-agentic/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt
│   ├── connections-stream.txt
│   ├── file-events.txt
│   ├── agentic-task-output.txt
│   ├── workspace-files.txt
│   ├── workspace-contents.txt
│   ├── agents-state-post-agentic.txt
│   └── new-files-during-agentic.txt
├── phase3c-selfmod/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── pstree-stream.txt
│   ├── skill-file-events.txt
│   ├── skills-before.txt
│   ├── skill-creation-output.txt
│   ├── skills-after.txt
│   ├── skills-diff.txt
│   └── skill-contents.txt
├── phase3d-proactive/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── cron-capabilities.txt
│   └── config-state.txt
├── phase4-teardown/
│   ├── EVIDENCE-HASHES.txt
│   ├── daemon-stop-output.txt
│   ├── remaining-processes.txt
│   ├── pstree-post-exit.txt
│   ├── port-18789-post-exit.txt
│   ├── connections-post-exit.txt
│   ├── connections-diff.txt
│   ├── listening-ports-post.txt
│   ├── openclaw-dir-final.txt
│   ├── openclaw-disk-final.txt
│   ├── home-tree-final.txt
│   ├── home-tree-diff.txt
│   ├── openclaw-artifacts-detail.txt
│   ├── shellprofile-diff-*.txt
│   ├── crontab-final.txt
│   ├── crontab-diff.txt
│   ├── launch-agents-final.txt
│   ├── launch-agents-diff.txt
│   └── auto-restart-check.txt
└── [Phase 5 analysis in LAB-RUN-007-RESULTS.md]
```

---

## Post-Run: Next Steps

1. **Complete the Section 5 analysis** — fill in every cell of the observation matrix, cross-class comparison table, and calculate the confidence score.
2. **Update the Playbook** — Section 4.11 IOCs with lab status, Section 12.1, Section 12.4, Section 12.5, Appendix B calibration data.
3. **File playbook feedback** for any IOCs that were predicted incorrectly or missing.
4. **Archive evidence** — compress `$LAB_DIR` and store per retention policy (Section 9.4).
5. **Plan next run** — OC-POS-02 (multi-channel messaging integration), OC-POS-03 (cron/proactive execution), OC-EVA-01 (renamed binary, custom port).
