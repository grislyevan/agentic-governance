# Lab Run Protocol: Claude Cowork Installation & Runtime Telemetry Capture

**Run ID:** LAB-RUN-014  
**Tool:** Claude Cowork (Claude Desktop v1.1.4498, `com.anthropic.claudefordesktop`)  
**Class:** C (Autonomous Executor) in Cowork mode; A (Assistive) in chat-only mode. Exhibits Class D indicators (scheduled tasks, self-modification via skill-creator, plugin extensibility) but lacks daemon persistence — proactive execution requires app to be running.  
**Playbook Reference:** Section 4.1b (Claude Cowork), Section 12 (Lab Validation), Appendix A (Cross-Layer Correlation Rules), Appendix B (Confidence Scoring)  
**INIT-43 Reference:** [init-issues/INIT-43-claude-process-file-network-signal-map.md](../init-issues/INIT-43-claude-process-file-network-signal-map.md) — process/file/network signal map, normalization fields, failure modes, correlation rules C1–C4, validation plan. Lab outputs must satisfy INIT-43 required outputs (per-layer report, confidence trace, correlation rule evaluation, residual ambiguity).  
**Target Scenario:** Positive — Standard install state capture + running state + session analysis + teardown  
**Scenario ID:** CW-POS-01  
**Status:** `COMPLETE`

---

## Prerequisites

### Environment

| Item | Requirement |
|---|---|
| **Platform** | macOS 26.3, Darwin 25.3.0, ARM64 (Apple Silicon M2) |
| **Shell** | zsh |
| **Root/sudo** | Not required |
| **Disk** | Claude Desktop: 564 MB app + 10 GB Application Support (VM images) |
| **Network** | Outbound internet access (Anthropic API, package registries via VM egress allowlist) |
| **Account** | Claude account (Pro/Max/Team/Enterprise) — authenticated via desktop app |

### Tool Availability Check

```bash
ls /Applications/Claude.app                    # App bundle present
plutil -p /Applications/Claude.app/Contents/Info.plist  # Version: 1.1.4498
codesign -dvvv /Applications/Claude.app        # Signed: Anthropic PBC (Q6L2SF6YDW)
which pstree lsof shasum                       # Detection tools present
```

### Evidence Directory Setup

```bash
export LAB_DIR=~/cowork-lab/LAB-RUN-014
mkdir -p "$LAB_DIR"/{baseline,phase1-install,phase2-onboard,phase3a-basic,phase3b-agentic,phase3c-selfmod,phase4-teardown}
mkdir -p ~/cowork-lab-workspace
```

### INIT-43 Signal Map Alignment

Captures in this protocol map to INIT-43 normalization and correlation as follows:

| INIT-43 layer | Normalization fields (INIT-43) | Protocol capture |
|---|---|---|
| **Process** | proc.path, parent_chain, child_chain, proc.signer | Phase 1: binary path, code-signing, entitlements. Phase 2: all-claude-processes (path, PID), pstree. Optional: pstree stream for session shape. |
| **File** | artifact.path, artifact.type, artifact.last_modified, artifact.repo_scope | Baseline: claude-desktop-dir, config paths. Phase 1: vm_bundles, local-agent-mode-sessions, app-support-breakdown (recency via timestamps). Trusted folder = repo_scope. |
| **Network** | net.dest_ip, net.conn_*, net.proc_link_confidence | Phase 2: claude-network-post-launch (PID per connection = process-to-connection linkage), dns-resolution. Optional: connections-stream for burst cadence. |

Correlation rules C1–C4 (Appendix A) are evaluated in Phase 5. Penalties (INIT-43 Section 6, Appendix B): missing parent-child chain, wrapper/renamed binary, stale artifact only, non-default paths, ambiguous proxy, unresolved process–network linkage, containerized/remote execution, weak identity.

---

## Pre-Install: Baseline Capture

**INIT-43:** Baseline establishes artifact.path, artifact.type, and recency reference for file layer; process and network state for comparison post-launch.

### File System Baseline

```bash
find ~ -maxdepth 4 -not -path '*/node_modules/*' -not -path '*/.cache/*' 2>/dev/null > "$LAB_DIR/baseline/home-tree.txt"
ls -laR ~/Library/Application\ Support/Claude/ > "$LAB_DIR/baseline/claude-desktop-dir.txt" 2>&1
ls -laR ~/.claude/ > "$LAB_DIR/baseline/claude-cli-dir.txt" 2>&1
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json > "$LAB_DIR/baseline/claude-desktop-config.txt" 2>&1
cat ~/Library/Application\ Support/Claude/Preferences > "$LAB_DIR/baseline/claude-desktop-preferences.txt" 2>&1
ls -la ~/Library/Application\ Support/Claude/Claude\ Extensions/ > "$LAB_DIR/baseline/claude-extensions.txt" 2>&1
ls -la ~/Library/Application\ Support/Claude/Claude\ Extensions\ Settings/ > "$LAB_DIR/baseline/claude-extensions-settings.txt" 2>&1
ls -la /tmp/ > "$LAB_DIR/baseline/tmp-listing.txt"
for f in ~/.bashrc ~/.bash_profile ~/.zshrc ~/.profile; do
  [ -f "$f" ] && cp "$f" "$LAB_DIR/baseline/$(basename $f).bak"
done
```

### Process Baseline

```bash
ps auxww > "$LAB_DIR/baseline/ps-full.txt"
pstree > "$LAB_DIR/baseline/pstree.txt" 2>/dev/null
ps auxww | grep -iE 'claude|anthropic|cowork' | grep -v grep > "$LAB_DIR/baseline/claude-process-check.txt" 2>&1
```

### Network Baseline

```bash
lsof -i -nP | grep LISTEN > "$LAB_DIR/baseline/listening-ports.txt"
lsof -i -nP > "$LAB_DIR/baseline/active-connections.txt"
```

### Environment Baseline

```bash
env | sort > "$LAB_DIR/baseline/env-vars.txt"
env | grep -iE 'anthropic|claude|openai|cowork' > "$LAB_DIR/baseline/ai-env.txt" 2>/dev/null
```

### Persistence Mechanism Baseline

```bash
crontab -l > "$LAB_DIR/baseline/crontab.txt" 2>&1
ls -la ~/Library/LaunchAgents/ > "$LAB_DIR/baseline/launch-agents.txt" 2>/dev/null
ls ~/Library/LaunchAgents/ | grep -iE 'claude|anthropic|cowork' > "$LAB_DIR/baseline/claude-plist-check.txt" 2>&1
```

### Create Baseline Timestamp Marker and Hashes

```bash
touch "$LAB_DIR/baseline/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/baseline/start-time.txt"
shasum -a 256 "$LAB_DIR/baseline/"* > "$LAB_DIR/baseline/EVIDENCE-HASHES.txt"
```

---

## Phase 1: Installation State Capture

Claude Desktop is distributed as a macOS app bundle. Cowork is a feature within the desktop app, not a separate install.

### App Bundle Metadata

```bash
file /Applications/Claude.app/Contents/MacOS/Claude > "$LAB_DIR/phase1-install/binary-metadata.txt"
ls -la /Applications/Claude.app/Contents/MacOS/Claude >> "$LAB_DIR/phase1-install/binary-metadata.txt"
shasum -a 256 /Applications/Claude.app/Contents/MacOS/Claude >> "$LAB_DIR/phase1-install/binary-metadata.txt"
codesign -dvvv /Applications/Claude.app > "$LAB_DIR/phase1-install/code-signing.txt" 2>&1
plutil -p /Applications/Claude.app/Contents/Info.plist > "$LAB_DIR/phase1-install/info-plist.txt"
codesign -d --entitlements :- /Applications/Claude.app > "$LAB_DIR/phase1-install/entitlements.txt" 2>&1
```

### Desktop Extensions (DXT)

```bash
ls -laR ~/Library/Application\ Support/Claude/Claude\ Extensions/ > "$LAB_DIR/phase1-install/claude-extensions-listing.txt"
cat ~/Library/Application\ Support/Claude/Claude\ Extensions/ant.dir.ant.anthropic.chrome-control/manifest.json > "$LAB_DIR/phase1-install/chrome-control-manifest.txt"
cat ~/Library/Application\ Support/Claude/Claude\ Extensions/ant.dir.ant.anthropic.notes/manifest.json > "$LAB_DIR/phase1-install/notes-manifest.txt"
```

### VM Bundle (Cowork Sandbox)

```bash
ls -laR ~/Library/Application\ Support/Claude/vm_bundles/ > "$LAB_DIR/phase1-install/vm-bundles.txt"
cat ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle/macAddress > "$LAB_DIR/phase1-install/vm-mac-address.txt"
cat ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle/vmIP > "$LAB_DIR/phase1-install/vm-ip.txt"
cat ~/Library/Application\ Support/Claude/vm_bundles/claudevm.bundle/machineIdentifier > "$LAB_DIR/phase1-install/vm-machine-id.txt"
```

### Disk Footprint

```bash
du -sh /Applications/Claude.app/ ~/Library/Application\ Support/Claude/ ~/.claude/ > "$LAB_DIR/phase1-install/app-disk-footprint.txt"
du -sh ~/Library/Application\ Support/Claude/*/ | sort -rh > "$LAB_DIR/phase1-install/app-support-breakdown.txt"
```

### Local Agent Mode Sessions

```bash
ls -laR ~/Library/Application\ Support/Claude/local-agent-mode-sessions/ > "$LAB_DIR/phase1-install/local-agent-sessions.txt"
```

### Phase 1 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase1-install/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase1-install/phase1-end-time.txt"
shasum -a 256 "$LAB_DIR/phase1-install/"* > "$LAB_DIR/phase1-install/EVIDENCE-HASHES.txt"
```

---

## Phase 2: Launch and Running State Capture

### Launch Claude Desktop

```bash
open -a "Claude"
sleep 15
```

### Post-Launch Process Capture

```bash
ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep > "$LAB_DIR/phase2-onboard/all-claude-processes.txt"
ps auxww | grep -iE 'claude|Virtualization.VirtualMachine' | grep -v grep | awk '{sum += $6} END {printf "Total RSS: %.1f MB\n", sum/1024}'
```

### Post-Launch Network Capture

```bash
lsof -i -nP 2>/dev/null | grep -i claude > "$LAB_DIR/phase2-onboard/claude-network-post-launch.txt"
# DNS resolution of connection targets
for ip in 160.79.104.10 34.200.175.163 34.36.57.103 18.97.36.61 57.144.104.128 98.87.131.13 35.190.46.17; do
  echo "$ip -> $(host $ip 2>/dev/null | head -1)"
done > "$LAB_DIR/phase2-onboard/dns-resolution.txt"
```

### Config State While Running

```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json > "$LAB_DIR/phase2-onboard/claude-config-running.txt"
cat ~/Library/Application\ Support/Claude/Preferences > "$LAB_DIR/phase2-onboard/preferences-running.txt"
```

### Optional: Connection and Process Stream Monitors (INIT-43 process–network linkage)

For process-to-connection linkage and burst cadence (INIT-43 network failure-mode mitigation), run in background; stop in Phase 4.

```bash
# Connection snapshot every 2 seconds (PID-attributable connections)
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
  lsof -i -nP 2>/dev/null | grep -i claude >> "$LAB_DIR/phase2-onboard/connections-stream.txt"
  sleep 2
done &
CONN_PID=$!
echo "CONN_PID=$CONN_PID" > "$LAB_DIR/phase2-onboard/monitor-pids.txt"

# Process snapshot every 2 seconds
while true; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
  ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep >> "$LAB_DIR/phase2-onboard/pstree-stream.txt"
  sleep 2
done &
PS_PID=$!
echo "PS_PID=$PS_PID" >> "$LAB_DIR/phase2-onboard/monitor-pids.txt"
```

### Phase 2 Timestamp and Hashes

```bash
touch "$LAB_DIR/phase2-onboard/TIMESTAMP_MARKER"
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase2-onboard/phase2-end-time.txt"
shasum -a 256 "$LAB_DIR/phase2-onboard/"* > "$LAB_DIR/phase2-onboard/EVIDENCE-HASHES.txt"
```

---

## Phase 3A: Session Data Analysis — Basic Interaction Evidence

Cowork interactions occur through the desktop GUI. Session data is captured by analyzing existing session artifacts.

### Session Metadata Extraction

```bash
SESSIONS_DIR=~/Library/Application\ Support/Claude/local-agent-mode-sessions/4d7e658e-fa3c-4ed0-acb2-2b0c8be0977c/d060ad95-efda-4d74-bb9d-9988057488c5
# List all sessions with titles and models
for f in "$SESSIONS_DIR"/local_*.json; do
  python3 -c "import json; d=json.load(open('$f')); print(d.get('title'), '|', d.get('model'))"
done > "$LAB_DIR/phase3a-basic/session-titles.txt"
```

### Audit Log Analysis

```bash
cp "$SESSIONS_DIR/local_febc7177-546a-4a6e-9a3f-77cfa20bee63/audit.jsonl" "$LAB_DIR/phase3a-basic/full-audit-log.jsonl"
# Extract tool_use_summary events, egress domains, system prompt
```

### Phase 3A Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3a-basic/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3a-basic/"* > "$LAB_DIR/phase3a-basic/EVIDENCE-HASHES.txt"
```

---

## Phase 3B: Agentic Execution — MCP Integration Evidence

Analyzed the "Optimize weekly calendar and schedule" session which used Google Calendar MCP connector.

### Agentic Audit Trail

56 audit events including 5 tool_use_summary entries showing:
- Retrieved Google Calendar events (multiple accounts)
- Listed available calendars
- Collected user preferences via questionnaire
- Multi-step calendar optimization

### Phase 3B Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3b-agentic/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3b-agentic/"* > "$LAB_DIR/phase3b-agentic/EVIDENCE-HASHES.txt"
```

---

## Phase 3C: Self-Modification — Skills and Plugin Infrastructure

### Built-in Skills

6 Anthropic-created skills: `skill-creator`, `xlsx`, `pptx`, `pdf`, `docx`, `schedule`

### Plugin Marketplace

Git clone of `anthropics/knowledge-work-plugins` with 19+ enterprise plugins.

### Schedule Skill — Proactive Execution Capability

The schedule skill creates autonomous recurring tasks with cron expressions. Combined with `coworkScheduledTasksEnabled: true` config, this enables proactive execution without user presence (while app is running).

### Phase 3C Timestamp and Hashes

```bash
touch "$LAB_DIR/phase3c-selfmod/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3c-selfmod/"* > "$LAB_DIR/phase3c-selfmod/EVIDENCE-HASHES.txt"
```

---

## Phase 4: Teardown — What Persists After Exit

### Stop Optional Monitors (if started in Phase 2)

```bash
[ -f "$LAB_DIR/phase2-onboard/monitor-pids.txt" ] && . "$LAB_DIR/phase2-onboard/monitor-pids.txt"
kill $CONN_PID $PS_PID 2>/dev/null
```

### Stop Claude Desktop

```bash
osascript -e 'tell application "Claude" to quit'
sleep 10
```

### Post-Quit Findings

- All 12 Claude processes stopped cleanly — zero orphans
- Zero network connections post-quit
- No LaunchAgents installed — no persistence mechanism
- No auto-restart after quit
- No shell profile modifications
- **10 GB persists** in `~/Library/Application Support/Claude/` (VM images, session data, plugin marketplace, extensions)
- VM `rootfs.img` and `sessiondata.img` modified during session (timestamps updated)

### Phase 4 Timestamp and Hashes

```bash
date -u +"%Y-%m-%dT%H:%M:%SZ" > "$LAB_DIR/phase4-teardown/phase4-end-time.txt"
shasum -a 256 "$LAB_DIR/phase4-teardown/"* > "$LAB_DIR/phase4-teardown/EVIDENCE-HASHES.txt"
```

### Master Evidence Hash

```bash
find "$LAB_DIR" -name 'EVIDENCE-HASHES.txt' -exec cat {} \; > "$LAB_DIR/MASTER-HASHES.txt"
shasum -a 256 "$LAB_DIR/MASTER-HASHES.txt" >> "$LAB_DIR/MASTER-HASHES.txt"
```

---

## Phases Executed

| Phase | Description | Outcome |
|---|---|---|
| Baseline | File, process, network, env, persistence capture | 20 evidence files |
| Phase 1 | Installation state capture (app already installed) | 31 evidence files. Key: VM bundle (9.6 GB), DXT extensions, session data |
| Phase 2 | Launch and running state capture | 17 evidence files. 12 processes, 546 MB RSS, 15 network connections |
| Phase 3A | Basic interaction — session data analysis | 19 evidence files. 4 sessions found with full audit trails |
| Phase 3B | Agentic execution — MCP integration evidence | 10 evidence files. Google Calendar integration confirmed |
| Phase 3C | Self-modification — skills/plugin infrastructure | 6 evidence files. Schedule skill, skill-creator, 19+ marketplace plugins |
| Phase 4 | Teardown — clean shutdown, persistence check | 9 evidence files. Clean exit, 10 GB passive persistence, no daemon |

---

## Phase 5: Evidence Analysis and Template Completion

Complete in [LAB-RUN-014-RESULTS.md](LAB-RUN-014-RESULTS.md). This section defines the required structure (INIT-43 required outputs).

### 5.1 Signal Observation Matrix

Fill in from captured evidence. For each layer, classify every IOC from Playbook Section 4.1b:

| Layer | IOC (from Section 4.1b) | Status | Evidence File | Notes |
|---|---|---|---|---|
| **Process** | Signed Claude Desktop app from `/Applications/Claude.app` | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Multi-process Electron + Virtualization.VirtualMachine VM process | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Process** | Plugin helper (DXT) and Network utility processes | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | `~/Library/Application Support/Claude/` (vm_bundles, local-agent-mode-sessions) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | Session JSON with identity, egress allowlist, audit.jsonl | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **File** | DXT extensions, skills plugin, plugin marketplace | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | Outbound TLS from Network utility process (PID-attributable) | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Network** | VM egress allowlist (session JSON), VM IP/MAC | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Identity** | accountName, emailAddress in session JSON; code signing | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | tool_use_summary in audit.jsonl; MCP connector activity | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |
| **Behavior** | schedule skill / coworkScheduledTasksEnabled; skill-creator | `[ ] Observed` `[ ] Different` `[ ] Not observed` | | |

### 5.2 Correlation Rule Evaluation (INIT-43 / Appendix A)

| Rule | Requirement | Result |
|---|---|---|
| **C1** High-confidence | Process entrypoint + lineage, at least one fresh artifact, network timing or behavioral continuity | `[ ] Met` `[ ] Not met` |
| **C2** Medium-confidence | Any two layers align; missing process certainty or artifact recency | `[ ] Met` `[ ] Not met` |
| **C3** Low-confidence | Single-layer only or conflicting signals | `[ ] Met` `[ ] Not met` |
| **C4** Ambiguity override | Layers conflict; downgrade to warn/approval only | `[ ] Met` `[ ] Not met` |

### 5.3 Confidence Score Calculation

Using Appendix B formula (five-layer defaults or Cowork-calibrated weights):

```
Layer Weights (Appendix B; Cowork proposed in LAB-RUN-014-RESULTS):
  Process:  0.25    File:  0.15 (default) / 0.20 (proposed)
  Network:  0.15    Identity:  0.10 (default) / 0.15 (proposed)
  Behavior: 0.15    Binary Hash: 0.20

Applicable penalties (INIT-43 Section 6, Appendix B):
  [ ] Missing parent-child process chain:          −0.15
  [ ] Wrapper/renamed binary without resolution:   −0.15
  [ ] Stale artifact only (no recent modification): −0.10
  [ ] Non-default artifact paths:                  −0.10
  [ ] Ambiguous proxy/gateway route:               −0.10
  [ ] Unresolved process-to-network linkage:       −0.10
  [ ] Containerized/remote execution:              −0.10
  [ ] Weak/missing identity correlation:           −0.10

final_confidence = max(0, base_score - penalties)
Classification: ≥0.75 High; 0.45–0.74 Medium; <0.45 Low
```

**Calculated score:** `___`  
**Classification:** `___`

### 5.4 Completed Lab Run Evidence Template (Playbook Section 12.2)

```
Run ID:              LAB-RUN-014
Date:                [execution date]
Tool:                Claude Cowork (Claude Desktop [version])
Scenario ID:         CW-POS-01
Environment:         [OS, endpoint posture, network]
Scenario Type:       Positive

Signal Observations:
  Process:           [observed / not observed — cite evidence files]
  File/Artifact:     [observed / not observed — cite evidence files]
  Network:           [observed / not observed — cite evidence files]
  Identity:          [observed / not observed — cite evidence files]
  Behavior:          [observed / not observed — cite evidence files]

Confidence Result:   [score + rationale]
Policy Decision:     [detect/warn/approval/block + rule_id]
Evidence Links:      [MASTER-HASHES.txt and phase evidence]
Pass/Fail:           [pass | conditional pass | fail]
Residual Risk:       [coverage gaps — INIT-43 "residual ambiguity notes"]
```

### 5.5 Findings and Playbook Feedback

| Finding | Affected Section | Recommended Change |
|---|---|---|
| | | |

---

## INIT-43 Validation Plan Coverage

From INIT-43 Section 7:

- **Positive checks:** (1) Canonical Cowork session with process/file/network alignment → CW-POS-01 (this run). (2) Multi-command/workflow with artifact and network corroboration → Phase 3B (MCP), session analysis. (3) Repeated session consistency → CW-POS-02 (scheduled task) when run.
- **Adversarial checks:** Non-standard install, VPN-routed API, DXT modification → follow-on CW-EVA-01; same four outputs required.
- **Required outputs (must appear in RESULTS):**
  1. **Per-layer signal capture report** → Section 1 "Signal Observation Matrix" in LAB-RUN-014-RESULTS.md
  2. **Confidence calculation trace** → Section 2 "Confidence Score Calculation" in LAB-RUN-014-RESULTS.md
  3. **Correlation rule evaluation** → Section 5.2 above; can be summarized in RESULTS
  4. **Residual ambiguity notes** → "Residual Risk" in completed evidence template (Section 5.4) and in RESULTS

---

## Evidence Inventory Checklist

When complete, `$LAB_DIR` should contain:

```
LAB-RUN-014/
├── MASTER-HASHES.txt
├── baseline/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── start-time.txt
│   ├── home-tree.txt
│   ├── claude-desktop-dir.txt
│   ├── claude-cli-dir.txt
│   ├── claude-desktop-config.txt
│   ├── claude-desktop-preferences.txt
│   ├── claude-extensions.txt
│   ├── claude-extensions-settings.txt
│   ├── tmp-listing.txt
│   ├── ps-full.txt
│   ├── pstree.txt
│   ├── claude-process-check.txt
│   ├── listening-ports.txt
│   ├── active-connections.txt
│   ├── env-vars.txt
│   ├── ai-env.txt
│   ├── crontab.txt
│   ├── launch-agents.txt
│   ├── claude-plist-check.txt
│   └── *.bak (shell profile backups)
├── phase1-install/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── phase1-end-time.txt
│   ├── binary-metadata.txt
│   ├── code-signing.txt
│   ├── info-plist.txt
│   ├── entitlements.txt
│   ├── claude-extensions-listing.txt
│   ├── chrome-control-manifest.txt
│   ├── notes-manifest.txt
│   ├── vm-bundles.txt
│   ├── vm-mac-address.txt
│   ├── vm-ip.txt
│   ├── vm-machine-id.txt
│   ├── app-disk-footprint.txt
│   ├── app-support-breakdown.txt
│   └── local-agent-sessions.txt
├── phase2-onboard/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── phase2-end-time.txt
│   ├── all-claude-processes.txt
│   ├── claude-network-post-launch.txt
│   ├── dns-resolution.txt
│   ├── claude-config-running.txt
│   ├── preferences-running.txt
│   ├── connections-stream.txt       (optional)
│   ├── pstree-stream.txt             (optional)
│   └── monitor-pids.txt             (optional)
├── phase3a-basic/
│   ├── EVIDENCE-HASHES.txt
│   ├── TIMESTAMP_MARKER
│   ├── session-titles.txt
│   └── full-audit-log.jsonl
├── phase3b-agentic/
│   ├── EVIDENCE-HASHES.txt
│   └── TIMESTAMP_MARKER
├── phase3c-selfmod/
│   ├── EVIDENCE-HASHES.txt
│   └── TIMESTAMP_MARKER
├── phase4-teardown/
│   ├── phase4-end-time.txt
│   └── EVIDENCE-HASHES.txt
└── [Phase 5 analysis in LAB-RUN-014-RESULTS.md]
```

---

## Post-Run: Next Steps

1. Complete Phase 5 analysis in LAB-RUN-014-RESULTS.md (signal matrix, correlation rules, confidence trace, evidence template, playbook feedback).
2. Update Playbook Section 12.5 Lab Run Log and Section 12.4 Methodology with any new findings.
3. If running CW-POS-02 / CW-POS-03 / skill-creator: use extended or scenario-specific protocols; produce same four INIT-43 outputs.
4. Archive evidence per retention policy (Section 9.4).

---

## Results

Full results: [LAB-RUN-014-RESULTS.md](LAB-RUN-014-RESULTS.md)

**Confidence:** 0.82 (High) — calibrated weights  
**Key finding:** Claude Cowork runs a full Linux VM via Apple Virtualization framework. The VM provides sandboxed execution with dedicated MAC address, IP, and EFI boot. Session data includes complete audit trails with identity, tool use summaries, and MCP connector activity. The 10 GB passive footprint is the largest of any profiled tool.
