# Calibration Pipeline Architecture

**Status:** Design (lab replay harness implemented; continuous scanning and drift monitoring are future)  
**Date:** 2026-03-11  
**Scope:** Confidence engine weight calibration, cross-tool regression, behavioral evolution detection

---

## 1. Problem

Confidence weights are hand-tuned from individual lab runs. Each lab run calibrates one tool in isolation. There is no automated check that tuning one tool's weights doesn't regress another's score. There is no mechanism to detect when a tool's new version shifts its detection profile. There is no feedback loop from production detections to weight refinement.

The playbook (Appendix B, Calibration Requirements) states:
- "Must be calibrated through lab replay runs"
- "Per-tool weight adjustments permitted when empirically justified"
- "All calibration changes must be versioned and traceable"

This document designs the pipeline that fulfills those requirements.

---

## 2. Three Components

```
┌─────────────────────────────────────────────────────────────────┐
│                    CALIBRATION PIPELINE                          │
│                                                                  │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │  Lab Replay   │   │  Continuous       │   │  Drift          │  │
│  │  Harness      │   │  Scanning         │   │  Monitoring     │  │
│  │               │   │                   │   │                 │  │
│  │  Replays      │   │  Runs scanner     │   │  Tracks score   │  │
│  │  stored lab   │   │  against live     │   │  distributions  │  │
│  │  observations │   │  tool installs    │   │  over time per  │  │
│  │  through the  │   │  on a schedule,   │   │  tool; alerts   │  │
│  │  confidence   │   │  captures new     │   │  when scores    │  │
│  │  engine.      │   │  fixtures.        │   │  drift beyond   │  │
│  │               │   │                   │   │  threshold.     │  │
│  │  Validates    │   │  Detects version- │   │                 │  │
│  │  band assign- │   │  to-version       │   │  Signals when   │  │
│  │  ments.       │   │  changes in tool  │   │  to recali-     │  │
│  │  Cross-tool   │   │  behavior.        │   │  brate.         │  │
│  │  regression.  │   │                   │   │                 │  │
│  └──────┬───────┘   └────────┬──────────┘   └───────┬────────┘  │
│         │                    │                       │           │
│         │   ┌────────────────┘                       │           │
│         │   │                                        │           │
│         ▼   ▼                                        │           │
│  ┌──────────────────┐                                │           │
│  │  Fixture Corpus   │◄──────────────────────────────┘           │
│  │  (JSON files)     │  Drift monitoring reads historical        │
│  │                   │  fixtures to establish baselines           │
│  └──────────────────┘                                            │
└─────────────────────────────────────────────────────────────────┘
```

### 2.1 Lab Replay Harness (build now)

**What it does:** Takes structured fixture files (one per lab run) containing observed signal strengths, penalties, and expected outcomes, and replays them through `compute_confidence()` and `classify_confidence()`. Validates that every fixture produces the expected confidence band. Runs as part of `pytest collector/tests/`.

**What it catches:**
- Weight changes that regress a different tool's band assignment
- Penalty interactions that push a borderline tool below a threshold
- Formula changes that break expected outcomes

**Fixture format:**

```json
{
  "lab_run": "LAB-RUN-001",
  "tool_name": "Claude Code",
  "tool_version": "2.1.59",
  "tool_class": "C",
  "platform": "macOS ARM64",
  "date": "2026-02-26",
  "signals": {
    "process": 0.85,
    "file": 0.95,
    "network": 0.30,
    "identity": 0.80,
    "behavior": 0.75
  },
  "penalties": [
    ["unresolved_proc_net_linkage", 0.05]
  ],
  "evasion_boost": 0.0,
  "expected_band": "Medium",
  "expected_score_range": [0.68, 0.74],
  "notes": "Network weakest without EDR. Polling cannot attribute to PID."
}
```

**`expected_score_range`** is a tolerance band (not an exact value) because minor weight adjustments should not require fixture updates unless they change the band. The primary assertion is on `expected_band`.

**Cross-tool regression test:** After all individual fixtures pass, the harness runs a regression check: for every pair of tools where one scores higher than the other in the fixture corpus, it verifies that the ordering is preserved with current weights. If tuning Claude Code's weights causes it to outscore Cursor (when the fixtures say Cursor should score higher), that's a regression.

### 2.2 Continuous Scanning (build later, when CI lab environment exists)

**What it does:** A CI job that runs the Detec scanner against pinned tool installations on a schedule (daily or weekly). Captures the `ScanResult` as a structured fixture and adds it to the corpus.

**What it catches:**
- Version-to-version changes in tool artifacts (new files, changed process trees, different network endpoints)
- New IOCs that weren't present in earlier versions
- Regressions in scanner detection (a tool update that breaks a scanner's pattern matching)

**Requirements:**
- CI environment with pinned tool installs (Claude Code, Cursor, Ollama, etc.)
- Each tool pinned to a known version, updated deliberately
- Scanner runs in `--dry-run --verbose` mode, captures `ScanResult`
- Output compared to the previous fixture for that tool; diffs are flagged for review

**Relationship to replay harness:** Continuous scanning produces new fixtures. The replay harness validates them. Together they form a feedback loop: scan a tool, capture the fixture, replay all fixtures (including the new one) to verify no regressions.

### 2.3 Drift Monitoring (build when dashboard is in production use)

**What it does:** Tracks per-tool confidence score distributions across the endpoint fleet over time. Alerts when a tool's median score drifts beyond a threshold without a corresponding change in the tool version or scanner code.

**What it catches:**
- Environmental changes that shift signal strengths (OS update changes process visibility, network config change affects connection capture)
- Fleet-wide calibration drift (scores gradually decrease as tool behavior evolves)
- Scanner degradation (a dependency update breaks a pattern match)

**Trigger:** When the 7-day rolling median for a tool's confidence score shifts by more than 0.10 from the baseline (established from the first 30 days of data), flag for recalibration review.

**Data source:** Detection events stored in the API database. The server computes the rolling median as a background task or on-demand report.

---

## 3. Fixture Corpus

All fixtures live in `collector/tests/fixtures/lab_runs/` as individual JSON files named `{lab_run_id}.json`. The harness discovers them by globbing the directory.

### Current corpus (from Playbook Appendix B)

| Fixture | Tool | Version | Class | Expected Band | Score Range |
|---------|------|---------|-------|---------------|-------------|
| LAB-RUN-001 | Claude Code | v2.1.59 | C | Medium | 0.68-0.74 |
| LAB-RUN-003 | Ollama | v0.17.0 | B | Medium | 0.66-0.72 |
| LAB-RUN-004 | Cursor | v2.5.26 | A/C | High | 0.76-0.82 |
| LAB-RUN-005 | GitHub Copilot | v0.37.9 (unauth) | A | Medium | 0.42-0.48 |
| LAB-RUN-006 | Open Interpreter | v0.4.3 | C | Medium | 0.50-0.56 |
| LAB-RUN-007 | OpenClaw | v2026.3.1 | D | High | 0.77-0.83 |
| LAB-RUN-013 | OpenClaw (local LLM) | v2026.3.1 | D | Medium | 0.66-0.72 |
| LAB-RUN-014 | Claude Cowork | v1.1.4498 | C | High | 0.86-0.92 |

### Adding new fixtures

When a new lab run is completed:
1. Record observed signal strengths, penalties, and expected band
2. Create a JSON fixture file following the format in Section 2.1
3. Run `pytest collector/tests/test_calibration.py` to verify the new fixture passes with current weights and that no existing fixtures regress
4. Commit the fixture alongside any weight adjustments

---

## 4. Weight Optimization (future)

When the fixture corpus grows large enough (20+ fixtures across tool versions), automated weight optimization becomes viable:

1. Define the objective: maximize the number of fixtures where the computed band matches `expected_band`
2. Search the weight space (grid search or Bayesian optimization) with the constraint that weights sum to 1.0 and each weight is in [0.05, 0.50]
3. The output is a proposed weight vector, not a deployed one. A human reviews the proposal, checks that the changes are justified, and merges
4. The replay harness validates the new weights against all fixtures before merge

This keeps the formula deterministic and auditable. The optimization selects weights; it does not replace the formula.

---

## 5. CI Automation

The replay harness runs automatically in GitHub Actions (`.github/workflows/ci.yml`):

- **Dedicated job:** "Calibration Regression" runs `pytest collector/tests/test_calibration.py -v` on every push and PR to main. Failures surface as a separate check, distinct from the general collector test suite.
- **General test suite:** The calibration tests also run as part of the "Collector Tests" job (`pytest collector/tests/`), providing redundant coverage.
- **Trigger scope:** Both jobs run on every code change, not filtered by path. This is intentional: a scanner logic change, a dependency update, or a seemingly unrelated refactor could affect confidence scoring. The harness is fast (<1 second) so there is no cost to running it on every change.

No manual invocation is needed. The three triggers described in Section 2.1 (weight changes, new fixtures, scanner logic changes) are all covered by "every push and PR to main."

---

## 6. Files

| File | Purpose |
|------|---------|
| `docs/architecture-calibration-pipeline.md` | This document |
| `collector/tests/fixtures/lab_runs/*.json` | Structured fixture files from lab run data |
| `collector/tests/test_calibration.py` | Replay harness: loads fixtures, validates scores and bands |
| `.github/workflows/ci.yml` | CI pipeline with dedicated "Calibration Regression" job |
