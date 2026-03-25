# Detection Review Cadence

The team runs a weekly detection quality review to track false positives, false negatives, and weight adjustment proposals across the labeled fixture corpus. All changes to confidence weights or policy values require evidence in the form of labeled fixtures — proposals without evidence are deferred until fixtures are provided.

## Weekly Review Agenda (30-minute meeting)

1. **Top 5 FP reports from the past week** — source: dashboard allow-list additions and analyst escalations. For each: confirm ground truth, check whether the fixture corpus captures the scenario, and decide if a new `fp`/`tn` fixture is warranted.

2. **Top 3 missed detections (FN) from the past week** — source: analyst reports of undetected AI tools. For each: identify which signal layers were weak, propose a `fn`-labeled fixture if one does not yet exist.

3. **Calibration metric regressions from CI** — review any failing `test_calibration.py` or `test_calibration_metrics.py` runs since the last meeting. Identify root cause (weight change, fixture staleness, new tool version).

4. **Weight/penalty adjustment proposals** — proposals must be tabled in the following format:

   | Signal / Penalty | Current value | Proposed value | Evidence fixture | Expected score delta |
   |------------------|--------------|----------------|-----------------|----------------------|
   | e.g. `network` weight (Claude Code) | 0.12 | 0.15 | LAB-RUN-001-linux.json | +0.01 |

5. **Decision log entry** — any approved change is recorded in the Decision Log below before the meeting closes.

## Decision Log Format

| Date | Change | Evidence | Before | After | Approved by |
|------|--------|----------|--------|-------|-------------|
| YYYY-MM-DD | Description of weight/penalty/threshold change | Fixture path(s) | Score or band before | Score or band after | Reviewer name |

## Thresholds for Action

- **FP rate on negative fixtures > 10%**: immediate weight review; no confidence model changes merge until FP rate is back below threshold.
- **Band accuracy < 95%**: block any confidence model changes until resolved; band accuracy is measured by `test_calibration.py` against all fixtures with `expected_band`.
- **Missed detection of Class C or D tool at High confidence**: incident review required; document in the decision log and open a tracking issue.

## Evidence Requirements for Weight Changes

- Must have at least one labeled fixture (`tp`/`tn`/`fp`/`fn`) showing the before-state (existing fixture that captures the current behaviour).
- Must have at least one labeled fixture showing the after-state — either a new fixture or an updated existing fixture with revised `expected_score_range` and a `notes` entry explaining the change.
- Must run the calibration replay harness locally before proposing any change:

  ```bash
  python -m pytest collector/tests/test_calibration.py collector/tests/test_calibration_metrics.py -v
  ```

- The PR must not be submitted until both the before and after fixtures are committed and the local harness passes.

---

Related: [docs/calibration-metrics.md](calibration-metrics.md) | [docs/architecture-calibration-pipeline.md](architecture-calibration-pipeline.md) | [CONTRIBUTING.md](../CONTRIBUTING.md)
