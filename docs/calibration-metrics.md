# Calibration Metrics (Accuracy)

**Purpose:** Define measurable targets for confidence-engine accuracy so regression and tuning work are testable. The replay harness in `test_calibration.py` proves band/range/order invariants; these metrics add detection-quality checks.

**See also:** [architecture-calibration-pipeline.md](architecture-calibration-pipeline.md) (fixture corpus, CI, weight optimization).

---

## 1. Metric definitions

### Band accuracy

Fraction of fixtures where the computed band matches the expected band:

- For each fixture: run `compute_confidence(scan)` then `classify_confidence(score)` and compare to `expected_band`.
- **Band accuracy** = (number of fixtures with matching band) / (total fixtures).
- Computed in the main replay harness; no label required.

### Precision and recall at policy-relevant thresholds

For a chosen score threshold (e.g. 0.45 for "Medium+", 0.75 for "High"):

- **Positive (ground truth):** fixtures with `label` in `tp` or `fn` (should be at or above threshold).
- **Negative (ground truth):** fixtures with `label` in `tn` or `fp`.
- **Predicted positive:** `compute_confidence(scan) >= threshold`.
- **Precision** = TP / (TP + FP).
- **Recall** = TP / (TP + FN).

Only fixtures with a `label` field participate. Implemented in `collector/tests/test_calibration_metrics.py`.

### False positive rate on clean baseline

For fixtures with `label` in `tn` or `fp` (ground truth negative):

- **FPR** = (number of those fixtures with predicted score >= threshold) / (total negative fixtures).
- Measures how often benign or negative cases are elevated above the threshold.

### Calibration error (ECE)

**Expected Calibrated Error:** confidence scores should be well calibrated (e.g. when we output 0.7 we should be correct about 70% of the time).

- Bin scores into N bins (e.g. 10). For each bin, compute mean predicted confidence and fraction of positives (from fixture labels).
- **ECE** = weighted sum over bins of (bin fraction) * |mean_confidence_in_bin - accuracy_in_bin|.
- Lower is better. Implemented in `test_calibration_metrics.py`; Brier score is optional for later.

---

## 2. Initial numeric targets (placeholders)

Refine these once the labeled corpus grows (Phase 1) and metrics tests run regularly.

| Metric | Initial target | Notes |
|--------|----------------|--------|
| Band accuracy | ≥ 95% on current corpus | Already enforced by replay harness. |
| Precision at 0.45 | No floor yet | Tighten when more labeled positives exist. |
| Recall at 0.45 | No floor yet | Same. |
| FPR on negative fixtures | &lt; 10% (lenient 50% in tests until corpus grows) | Reduce target as negatives are added. |
| ECE | &lt; 0.10 (lenient 0.20 in tests until corpus grows) | Tighten when corpus and labels expand. |

---

## 3. Where metrics are computed

- **Band accuracy:** Implicit in `test_calibration.py` (each fixture must match `expected_band`).
- **Precision / recall / FPR / ECE:** `collector/tests/test_calibration_metrics.py`, using only fixtures with `label` (tp/fp/tn/fn). CI runs this in the same job as the calibration replay harness (see `.github/workflows/ci.yml`).

Targets in this doc are referenced when adding or tightening assertions in the metrics tests and when running the Phase 4 weight optimization (macro-F1 + calibration quality).
