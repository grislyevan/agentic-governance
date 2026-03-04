# LAB-RUN-008 Template: Aider Installation & Runtime Telemetry

**Run ID:** LAB-RUN-008  
**Status:** PENDING — scanner written, awaiting tool installation  
**Tool:** Aider (aider-chat pip package, latest stable)  
**Scenario ID:** AI-POS-01 (Standard install + repo editing session)  
**Environment:** macOS 26.x, Darwin 25.x, ARM64 (Apple Silicon)  
**Scenario Type:** Positive  

---

## Pre-Run Checklist

- [ ] Install aider: `pip install aider-chat`
- [ ] Configure API key: `export OPENAI_API_KEY=...` or `export ANTHROPIC_API_KEY=...`
- [ ] Create test git repo: `mkdir ~/aider-lab && cd ~/aider-lab && git init && git commit --allow-empty -m "init"`
- [ ] Run aider on test task: `aider --model gpt-4o --yes test.py`
- [ ] Let aider make at least 2 commits
- [ ] Run collector: `cd collector && python main.py --dry-run --verbose`
- [ ] Capture output and verify Aider scanner detects correctly

---

## Signal Observation Targets

### Process Layer
- [ ] `aider` CLI process visible via `pgrep -fl aider`
- [ ] Child processes: git, python, shell subprocesses during editing
- [ ] Process user: current OS user

### File Layer
- [ ] `.aider.conf.yml` or `.aider.chat.history.md` in test repo
- [ ] `aider-chat` package in pip: `pip show aider-chat`
- [ ] `~/.aider/` cache directory (if created)

### Network Layer
- [ ] TLS connections to LLM API endpoint (api.openai.com or api.anthropic.com)
- [ ] Connection visible via `lsof -i -n -P` during active session

### Identity Layer
- [ ] OS user mapped to process: `ps -p <pid> -o user=`
- [ ] Git user.email matches commit author
- [ ] API key present in environment

### Behavior Layer
- [ ] Prompt-edit-commit loop confirmed (aider → git child → commit)
- [ ] `.aider*` artifact recency (modified within 24h)
- [ ] Git commits with aider attribution pattern in subject line

---

## Expected Scanner Output

```
Confidence: ~0.65–0.75 (Medium–High)
Tool class: C
Policy: warn or approval_required
```

---

## Calibration Notes

*(Fill in after running)*

| Layer | Expected Weight | Observed Signal | Calibration Adjustment |
|---|---|---|---|
| Process | 0.30 | — | — |
| File | 0.25 | — | — |
| Network | 0.15 | — | — |
| Identity | 0.15 | — | — |
| Behavior | 0.15 | — | — |

---

## Post-Run Actions

- [ ] Update `AiderScanner` with any calibration adjustments
- [ ] Update playbook section 4.8 with lab-validated signal strengths
- [ ] Mark LAB-RUN-008 as complete in PROGRESS.md
- [ ] Bump playbook version if findings require updates
