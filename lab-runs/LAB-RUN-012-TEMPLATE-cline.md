# LAB-RUN-012 Template: Cline IDE Extension Installation & Runtime Telemetry

**Run ID:** LAB-RUN-012  
**Status:** PENDING — scanner written, awaiting extension installation  
**Tool:** Cline extension (saoudrizwan.claude-dev, latest stable)  
**Scenario ID:** CLINE-POS-01 (Install + multi-file edit task + Class C tool-call escalation)  
**Environment:** VS Code or Cursor, macOS 26.x, ARM64  
**Scenario Type:** Positive + Class escalation (A → C on tool-call)  

---

## Pre-Run Checklist

- [ ] Install Cline in VS Code or Cursor (search "Cline" or install `saoudrizwan.claude-dev`)
- [ ] Configure API key (Anthropic or OpenAI)
- [ ] Run a task that involves file writes and/or shell execution (Class C trigger)
- [ ] Run collector: `cd collector && python main.py --dry-run --verbose`
- [ ] Capture output and verify Cline scanner detects correctly, including class escalation

---

## Signal Observation Targets

### Process Layer
- [ ] IDE extension host visible via `pgrep -fl extensionHost`

### File Layer
- [ ] Extension directory: `saoudrizwan.claude-dev-*` in VS Code or Cursor extensions
- [ ] Task history: `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/tasks/`
- [ ] `ui_messages.json` in latest task dir contains write/exec tool calls
- [ ] `api_conversation_history.json` with message count

### Network Layer
- [ ] TLS connections from extension host PIDs to api.anthropic.com or api.openai.com

### Identity Layer
- [ ] OS user and API key in environment

### Behavior Layer
- [ ] write_to_file / execute_command / browser_action in ui_messages.json → Class C
- [ ] Recent task directory (modified within 1h)
- [ ] Task count in history

---

## Expected Scanner Output

```
Confidence: ~0.65–0.80 (Medium–High)
Tool class: C (when tool-calling active), A (install-only)
Policy: approval_required (Class C + R3 writes)
```

---

## Key Validation Points

1. Class escalation: scanner must report Class C when `write_to_file` or `execute_command` is present in `ui_messages.json`
2. Class A reported if extension is installed but no tool-call history exists
3. Version detected from `package.json` in extension directory

---

## Calibration Notes

*(Fill in after running)*

| Layer | Expected Weight | Observed Signal | Calibration Adjustment |
|---|---|---|---|
| Process | 0.20 | — | — |
| File | 0.35 | — | — |
| Network | 0.15 | — | — |
| Identity | 0.10 | — | — |
| Behavior | 0.20 | — | — |
