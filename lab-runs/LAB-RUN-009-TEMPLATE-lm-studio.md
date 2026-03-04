# LAB-RUN-009 Template: LM Studio Installation & Runtime Telemetry

**Run ID:** LAB-RUN-009  
**Status:** PENDING — scanner written, awaiting tool installation  
**Tool:** LM Studio (latest stable, macOS dmg installer)  
**Scenario ID:** LMS-POS-01 (Install + model download + local server mode)  
**Environment:** macOS 26.x, Darwin 25.x, ARM64 (Apple Silicon)  
**Scenario Type:** Positive  

---

## Pre-Run Checklist

- [ ] Download and install LM Studio from lmstudio.ai
- [ ] Download at least one GGUF model (e.g., Llama 3.2 3B)
- [ ] Enable local server mode: LM Studio → Local Server → Start Server
- [ ] Verify server responds: `curl http://localhost:1234/v1/models`
- [ ] Run collector: `cd collector && python main.py --dry-run --verbose`
- [ ] Capture output and verify LM Studio scanner detects correctly

---

## Signal Observation Targets

### Process Layer
- [ ] `LM Studio` Electron process visible via `pgrep -fl "LM Studio"`
- [ ] Process user: current OS user

### File Layer
- [ ] `/Applications/LM Studio.app` installed
- [ ] `~/Library/Application Support/LM Studio/` data directory
- [ ] GGUF model files in configured model path
- [ ] Model storage size (GB) recorded

### Network Layer
- [ ] `localhost:1234` listener visible via `lsof -i :1234`
- [ ] `/v1/models` API returns loaded model list
- [ ] API is unauthenticated (risk marker)

### Identity Layer
- [ ] OS user mapped to process
- [ ] No external credential needed (local-only)

### Behavior Layer
- [ ] App running + models loaded = active inference capable
- [ ] Recent model file access (within 24h)

---

## Expected Scanner Output

```
Confidence: ~0.65–0.80 (Medium–High)
Tool class: B
Policy: warn
```

---

## Calibration Notes

*(Fill in after running)*

| Layer | Expected Weight | Observed Signal | Calibration Adjustment |
|---|---|---|---|
| Process | 0.25 | — | — |
| File | 0.30 | — | — |
| Network | 0.20 | — | — |
| Identity | 0.10 | — | — |
| Behavior | 0.15 | — | — |

---

## Post-Run Actions

- [ ] Update `LMStudioScanner` with calibration adjustments
- [ ] Update playbook section 4.5 with lab-validated signal strengths
- [ ] Mark LAB-RUN-009 as complete in PROGRESS.md
