# LAB-RUN-010 Template: Continue IDE Extension Installation & Runtime Telemetry

**Run ID:** LAB-RUN-010  
**Status:** PENDING — scanner written, awaiting extension installation  
**Tool:** Continue extension (continue.continue, latest stable)  
**Scenario ID:** CONT-POS-01 (Install + config + Ollama backend + active coding session)  
**Environment:** VS Code or Cursor, macOS 26.x, ARM64  
**Scenario Type:** Positive + Escalation (unapproved Ollama backend)  

---

## Pre-Run Checklist

- [ ] Install Continue extension in VS Code or Cursor
- [ ] Configure Ollama as backend in `~/.continue/config.json`
- [ ] Complete at least one active coding session (inline suggestions + chat)
- [ ] Run collector: `cd collector && python main.py --dry-run --verbose`
- [ ] Capture output and verify Continue scanner detects correctly

---

## Signal Observation Targets

### Process Layer
- [ ] IDE extension host visible via `pgrep -fl extensionHost`

### File Layer
- [ ] `~/.continue/config.json` exists with backend configuration
- [ ] Extension directory: `~/.vscode/extensions/continue.continue-*` or Cursor equivalent
- [ ] GlobalStorage: `~/Library/Application Support/Code/User/globalStorage/continue.continue/`
- [ ] Backend config: provider field (ollama = unapproved backend)

### Network Layer
- [ ] Connection to `:11434` (Ollama) from extension host PIDs → unapproved backend active
- [ ] Or TLS connection to api.anthropic.com / api.openai.com

### Identity Layer
- [ ] OS user mapped to IDE process

### Behavior Layer
- [ ] Files modified in `~/.continue/` within last hour
- [ ] Unapproved backend configured and active (risk escalation)

---

## Expected Scanner Output

```
Confidence: ~0.55–0.70 (Medium)
Tool class: A
Policy: warn (escalated by unapproved backend)
```

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
