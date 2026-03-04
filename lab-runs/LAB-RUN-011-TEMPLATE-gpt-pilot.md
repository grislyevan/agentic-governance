# LAB-RUN-011 Template: GPT-Pilot Installation & Runtime Telemetry

**Run ID:** LAB-RUN-011  
**Status:** PENDING — scanner written, awaiting tool installation  
**Tool:** GPT-Pilot / Pythagora (pip install gpt-pilot, latest stable)  
**Scenario ID:** GPT-POS-01 (Install + project generation task)  
**Environment:** macOS 26.x, Darwin 25.x, ARM64  
**Scenario Type:** Positive  

---

## Pre-Run Checklist

- [ ] Install: `pip install gpt-pilot` (or `pythagora`)
- [ ] Configure API key: `export OPENAI_API_KEY=...`
- [ ] Run a project generation task in a test workspace directory
- [ ] Run collector during generation: `cd collector && python main.py --dry-run --verbose`
- [ ] Capture output and verify GPT-Pilot scanner detects correctly

---

## Signal Observation Targets

### Process Layer
- [ ] `gpt-pilot` or `pythagora` process visible via `pgrep -fl`
- [ ] Child processes: python, node, npm, pip, bash during generation loop
- [ ] Long-lived orchestration process (minutes, not seconds)

### File Layer
- [ ] `.gpt-pilot/` state directory in project workspace
- [ ] Package installed: `pip show gpt-pilot`
- [ ] High file count in generated project tree

### Network Layer
- [ ] API burst cycles to OpenAI/Anthropic during generation phases

### Identity Layer
- [ ] OS user and API key in environment

### Behavior Layer
- [ ] High file churn: 20+ files created in last hour
- [ ] Generate→validate→regenerate cycle visible in child processes

---

## Expected Scanner Output

```
Confidence: ~0.60–0.75 (Medium–High)
Tool class: C
Policy: approval_required (R3 action risk from mass generation)
```

---

## Calibration Notes

*(Fill in after running)*

| Layer | Expected Weight | Observed Signal | Calibration Adjustment |
|---|---|---|---|
| Process | 0.25 | — | — |
| File | 0.20 | — | — |
| Network | 0.15 | — | — |
| Identity | 0.10 | — | — |
| Behavior | 0.30 | — | — |
