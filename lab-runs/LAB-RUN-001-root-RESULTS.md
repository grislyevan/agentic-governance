# LAB-RUN-001-root Results: Claude Code with Root/Full Visibility

**Run ID:** LAB-RUN-001-root  
**Date:** _fill after run_  
**Tool:** Claude Code (`@anthropic-ai/claude-code`)  
**Scenario ID:** CC-POS-01 (same as LAB-RUN-001; run with root for tcpdump and process-to-network linkage)  
**Environment:** _e.g. macOS 26.x, Darwin 25.x, ARM64, managed endpoint_  
**Evidence Directory:** `~/claude-lab/LAB-RUN-001-root/`

---

## 1. Signal Observation Matrix

Fill per-layer from evidence. With root you should have:

- **Process:** Same as LAB-RUN-001 or better (clear lineage).
- **File:** Same (0.95).
- **Network:** **Improve here** — use pcap to confirm TLS/SNI to `api.anthropic.com` / `claude.ai` and attribute to claude PID. Set layer signal strength (e.g. 0.55–0.75) and note if **unresolved_proc_net_linkage** is no longer applied.
- **Identity / Behavior:** Same as LAB-RUN-001 unless you note differences.

| Layer   | Signal strength | Notes |
|--------|------------------|-------|
| Process | _fill_           | _e.g. 0.85–0.90_ |
| File    | _fill_           | _e.g. 0.95_ |
| Network | _fill_           | _with pcap attribution_ |
| Identity| _fill_           | _e.g. 0.80_ |
| Behavior| _fill_           | _e.g. 0.75–0.90_ |

---

## 2. Correlation Rule Evaluation (C1–C4)

| Rule | Description | Met / Not met |
|------|-------------|----------------|
| C1    | High-confidence: process + artifact + network or behavior | `[ ] Met` `[ ] Not met` |
| C2    | Medium-confidence: two layers align | `[ ] Met` `[ ] Not met` |
| C3    | Low-confidence: single layer or conflicting | `[ ] Met` `[ ] Not met` |
| C4    | Ambiguity override | `[ ] Met` `[ ] Not met` |

---

## 3. Confidence Score

### Penalties

- **Unresolved process-to-network linkage:** With pcap + PID attribution this may be **0** (no penalty). If still partial, use −0.05.
- Other penalties: same as LAB-RUN-001 unless you observe wrapper/renamed binary, stale artifact only, etc.

### Final score and band

```
base_score   = _fill from five-layer weights_
penalties    = _fill (0 or 0.05)_
final_confidence = _fill_

Classification: _Medium / High_
```

---

## 4. Completed Lab Run Evidence Template

Fill the same template format as in LAB-RUN-001-RESULTS Section 4 (Run ID, Date, Tool, Scenario ID, Environment, Signal Observations, Confidence Result, Policy Decision, Evidence Links, Pass/Fail, Residual Risk).

---

## 5. Playbook / Calibration Notes

- **Fixture:** After filling this doc, add or update `collector/tests/fixtures/lab_runs/LAB-RUN-001-root.json` (or update `LAB-RUN-001.json`) with the observed signals, penalties, and expected_band. Run `pytest collector/tests/test_calibration.py`.
- **Weights:** If the band is High, consider documenting in playbook that CC-POS-01 with full visibility (root/EDR) achieves High; optionally leave `CLAUDE_CODE_WEIGHTS` as-is and use the root fixture only for regression.
