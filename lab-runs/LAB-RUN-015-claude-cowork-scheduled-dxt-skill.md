# Lab Run Protocol: Claude Cowork Gap Scenarios (Scheduled Task, DXT, Skill-Creator)

**Run ID:** LAB-RUN-015  
**Tool:** Claude Cowork (Claude Desktop, same as LAB-RUN-014)  
**Prerequisite:** LAB-RUN-014 (CW-POS-01) completed; Claude Desktop installed and run at least once.  
**Scenarios:** CW-POS-02 (scheduled task), CW-POS-03 (DXT chrome-control), skill-creator (self-modification)  
**Playbook Reference:** Section 4.1b, Section 12.1 validation matrix, INIT-43 required outputs  
**Status:** `PENDING`

---

## Scope

This protocol extends LAB-RUN-014 by exercising three behaviors that were architecturally confirmed but not fully exercised in CW-POS-01:

| Scenario | Phase | Purpose | INIT-43 relevance |
|----------|--------|---------|-------------------|
| **CW-POS-02** | 3D | Scheduled task creation and execution (schedule skill + coworkScheduledTasksEnabled) | Repeated session consistency; behavioral + process evidence for "soft proactive" |
| **CW-POS-03** | 3E | DXT browser automation (chrome-control: tabs, JS execution, page content) | Process child fan-out (AppleScript/Chrome); behavior layer |
| **Skill-creator** | 3F | Agent creates or modifies a skill via skill-creator | File artifact recency; self-modification behavior |

Each scenario produces the same four INIT-43 required outputs: per-layer signal report, confidence trace, correlation rule evaluation, residual ambiguity (see end of this doc).

---

## Prerequisites

- Same environment as LAB-RUN-014 (macOS, zsh, Claude Desktop installed).
- `coworkScheduledTasksEnabled: true` in `~/Library/Application Support/Claude/claude_desktop_config.json` for CW-POS-02.
- Chrome installed for CW-POS-03 (chrome-control DXT uses Chrome AppleScript API).
- Evidence dir can reuse LAB-RUN-014 or use a new run dir.

### Evidence Directory (optional separate run)

```bash
export LAB_DIR=~/cowork-lab/LAB-RUN-015
mkdir -p "$LAB_DIR"/{baseline,phase3d-scheduled,phase3e-dxt,phase3f-skillcreator}
```

If reusing LAB-RUN-014 evidence, set `LAB_DIR=~/cowork-lab/LAB-RUN-014` and add phase dirs:

```bash
mkdir -p "$LAB_DIR/phase3d-scheduled" "$LAB_DIR/phase3e-dxt" "$LAB_DIR/phase3f-skillcreator"
```

---

## Phase 3D: CW-POS-02 — Scheduled Task Exercise

**Goal:** Create a recurring task via the `schedule` skill and capture process/artifact/network when the task runs (while app is open).

### Pre-exercise capture

```bash
touch "$LAB_DIR/phase3d-scheduled/TIMESTAMP_PRE"
ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep > "$LAB_DIR/phase3d-scheduled/processes-before.txt"
lsof -i -nP 2>/dev/null | grep -i claude > "$LAB_DIR/phase3d-scheduled/network-before.txt"
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | grep -i schedule > "$LAB_DIR/phase3d-scheduled/config-schedule-flag.txt"
```

### Exercise

1. In Claude Cowork, start a session and ask the agent to create a **recurring scheduled task** (e.g. "Schedule a task to run every 2 minutes that writes the current time to a file in ~/cowork-lab-workspace/scheduled-output.txt").
2. Confirm the schedule skill is used and the task is registered.
3. Leave the app open and wait for at least one scheduled execution (e.g. 2 minutes).
4. Optionally run a short process/connection monitor during the wait:

```bash
for i in 1 2 3 4 5 6 7 8 9 10; do
  echo "=== $(date -u +%H:%M:%S) ===" >> "$LAB_DIR/phase3d-scheduled/pstree-sample.txt"
  ps auxww | grep -iE 'claude|Virtualization' | grep -v grep >> "$LAB_DIR/phase3d-scheduled/pstree-sample.txt"
  sleep 12
done
```

### Post-exercise capture

```bash
ps auxww | grep -iE 'claude|anthropic|Virtualization' | grep -v grep > "$LAB_DIR/phase3d-scheduled/processes-after.txt"
lsof -i -nP 2>/dev/null | grep -i claude > "$LAB_DIR/phase3d-scheduled/network-after.txt"
ls -la ~/cowork-lab-workspace/scheduled-output.txt > "$LAB_DIR/phase3d-scheduled/scheduled-output-artifact.txt" 2>&1
cat ~/cowork-lab-workspace/scheduled-output.txt >> "$LAB_DIR/phase3d-scheduled/scheduled-output-artifact.txt" 2>/dev/null
# Session audit trail for the schedule session (replace SESSIONS_DIR with actual path from local-agent-mode-sessions)
# find ~/Library/Application\ Support/Claude/local-agent-mode-sessions -name "audit.jsonl" -newer "$LAB_DIR/phase3d-scheduled/TIMESTAMP_PRE" -exec cp {} "$LAB_DIR/phase3d-scheduled/audit-schedule-session.jsonl" \;
touch "$LAB_DIR/phase3d-scheduled/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3d-scheduled/"* > "$LAB_DIR/phase3d-scheduled/EVIDENCE-HASHES.txt" 2>/dev/null
```

**Phase 5 (3D):** In RESULTS, document: process/behavior signals observed during scheduled run; whether scheduled execution is visible in process tree; residual risk (e.g. no LaunchAgent, task only while app open).

---

## Phase 3E: CW-POS-03 — DXT Chrome-Control Exercise

**Goal:** Use the chrome-control extension (open URL, execute JS, get page content) and capture host-side process spawning and any new artifacts.

### Pre-exercise capture

```bash
touch "$LAB_DIR/phase3e-dxt/TIMESTAMP_PRE"
ps auxww | grep -iE 'claude|Chrome|Safari|AppleScript' | grep -v grep > "$LAB_DIR/phase3e-dxt/processes-before.txt"
```

### Exercise

1. In Claude Cowork, start a session and ask the agent to use **browser automation** (e.g. "Open https://example.com in Chrome and tell me the title of the page" or "Use Chrome to run a simple JavaScript snippet and return the result").
2. Ensure the chrome-control DXT is invoked (may require enabling or confirming the extension).
3. Observe: Chrome or AppleScript processes spawned from Claude Desktop.

### Post-exercise capture

```bash
ps auxww | grep -iE 'claude|Chrome|Safari|AppleScript' | grep -v grep > "$LAB_DIR/phase3e-dxt/processes-after.txt"
lsof -i -nP 2>/dev/null | grep -i claude > "$LAB_DIR/phase3e-dxt/network-after.txt"
# DXT extension state
ls -laR ~/Library/Application\ Support/Claude/Claude\ Extensions/ > "$LAB_DIR/phase3e-dxt/extensions-after.txt"
touch "$LAB_DIR/phase3e-dxt/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3e-dxt/"* > "$LAB_DIR/phase3e-dxt/EVIDENCE-HASHES.txt" 2>/dev/null
```

**Phase 5 (3E):** In RESULTS, document: process child fan-out (Chrome/AppleScript PIDs); behavior layer (browser automation); residual risk (host-side automation outside VM sandbox).

---

## Phase 3F: Skill-Creator (Self-Modification) Exercise

**Goal:** Have the agent create or modify a skill via the skill-creator skill; capture file writes under skills/plugin paths and audit trail.

### Pre-exercise capture

```bash
touch "$LAB_DIR/phase3f-skillcreator/TIMESTAMP_PRE"
find ~/Library/Application\ Support/Claude -name "*.py" -path "*skill*" 2>/dev/null | head -50 > "$LAB_DIR/phase3f-skillcreator/skills-before.txt"
ls -laR ~/Library/Application\ Support/Claude/Claude\ Extensions/ 2>/dev/null | head -200 > "$LAB_DIR/phase3f-skillcreator/extensions-before.txt"
```

### Exercise

1. In Claude Cowork, start a session and ask the agent to **create or modify a skill** (e.g. "Use the skill-creator to add a simple skill that returns the current date" or "Modify an existing skill to add a new capability").
2. Confirm the skill-creator skill is used and that files are written (e.g. under extensions or a skills directory).
3. Note any approval prompts (or absence thereof).

### Post-exercise capture

```bash
find ~/Library/Application\ Support/Claude -name "*.py" -path "*skill*" 2>/dev/null | head -50 > "$LAB_DIR/phase3f-skillcreator/skills-after.txt"
find ~/Library/Application\ Support/Claude -newer "$LAB_DIR/phase3f-skillcreator/TIMESTAMP_PRE" -type f 2>/dev/null > "$LAB_DIR/phase3f-skillcreator/files-changed.txt"
ls -laR ~/Library/Application\ Support/Claude/Claude\ Extensions/ 2>/dev/null | head -200 > "$LAB_DIR/phase3f-skillcreator/extensions-after.txt"
# Copy most recent audit.jsonl that mentions skill (manual if needed)
touch "$LAB_DIR/phase3f-skillcreator/TIMESTAMP_MARKER"
shasum -a 256 "$LAB_DIR/phase3f-skillcreator/"* > "$LAB_DIR/phase3f-skillcreator/EVIDENCE-HASHES.txt" 2>/dev/null
```

**Phase 5 (3F):** In RESULTS, document: file artifact recency (new/modified skill files); behavior (self-modification without approval gate); residual risk.

---

## INIT-43 Required Outputs (per scenario or combined)

For each of 3D, 3E, 3F (or in a single LAB-RUN-015-RESULTS.md), produce:

1. **Per-layer signal capture report** — Signal Observation Matrix rows for process, file, network, identity, behavior relevant to that scenario.
2. **Confidence calculation trace** — No change to overall tool confidence expected; note any scenario-specific signal strength delta.
3. **Correlation rule evaluation** — C1–C4: confirm alignment (e.g. process + artifact + behavior for scheduled run).
4. **Residual ambiguity notes** — Residual Risk: coverage gaps (e.g. scheduled task not observed at exact execution moment; DXT host process attribution; skill-creator approval gate).

---

## Evidence Inventory (LAB-RUN-015)

```
LAB-RUN-015/
├── baseline/                    (optional; or reuse 014)
├── phase3d-scheduled/
│   ├── TIMESTAMP_PRE
│   ├── TIMESTAMP_MARKER
│   ├── EVIDENCE-HASHES.txt
│   ├── processes-before.txt
│   ├── processes-after.txt
│   ├── network-before.txt
│   ├── network-after.txt
│   ├── config-schedule-flag.txt
│   ├── scheduled-output-artifact.txt
│   └── pstree-sample.txt        (optional)
├── phase3e-dxt/
│   ├── TIMESTAMP_PRE
│   ├── TIMESTAMP_MARKER
│   ├── EVIDENCE-HASHES.txt
│   ├── processes-before.txt
│   ├── processes-after.txt
│   ├── network-after.txt
│   └── extensions-after.txt
├── phase3f-skillcreator/
│   ├── TIMESTAMP_PRE
│   ├── TIMESTAMP_MARKER
│   ├── EVIDENCE-HASHES.txt
│   ├── skills-before.txt
│   ├── skills-after.txt
│   ├── files-changed.txt
│   ├── extensions-before.txt
│   └── extensions-after.txt
└── LAB-RUN-015-RESULTS.md       (Phase 5 analysis for 3D, 3E, 3F)
```

---

## Post-Run

1. Complete Phase 5 analysis for 3D, 3E, 3F in LAB-RUN-015-RESULTS.md (or append to LAB-RUN-014-RESULTS.md).
2. Update Playbook Section 12.5 and validation matrix (12.1) with CW-POS-02 / CW-POS-03 status.
3. Feed findings into Section 4.1b and Section 12.4 Methodology (e.g. "soft proactive" classification, DXT host-side IOC).
