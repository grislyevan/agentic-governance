"""Calibration accuracy metrics: precision, recall, FPR, ECE over labeled fixtures.

Uses the same fixture corpus as test_calibration.py. Only fixtures with a
`label` field (tp/fp/tn/fn) participate in precision/recall/ECE. Tests
skip or use lenient thresholds when the labeled fixture set is small.

Run: pytest collector/tests/test_calibration_metrics.py -v
"""

from __future__ import annotations

import unittest
from pathlib import Path

from engine.confidence import compute_confidence, classify_confidence

from collector.tests.test_calibration import (
    FIXTURE_DIR,
    LabFixture,
    _load_all_fixtures,
)

# Policy-relevant thresholds (align with classify_confidence)
THRESHOLD_MEDIUM_PLUS = 0.45
THRESHOLD_HIGH = 0.75

# Minimum labeled fixtures to run metrics (otherwise skip)
MIN_LABELED_FOR_METRICS = 2
MIN_LABELED_FOR_ECE = 2

# Lenient bounds until corpus grows (tighten when Phase 1 expands corpus)
ECE_MAX_LENIENT = 0.20
FPR_MAX_LENIENT = 0.5


def _labeled_fixtures(fixtures: list[LabFixture]) -> list[LabFixture]:
    return [f for f in fixtures if f.label in ("tp", "fp", "tn", "fn")]


def _precision_recall_at_threshold(
    fixtures: list[LabFixture],
    threshold: float,
) -> tuple[float, float, int, int, int, int]:
    """Compute precision and recall at a score threshold. Returns (precision, recall, tp, fp, tn, fn)."""
    tp = fp = tn = fn = 0
    for f in fixtures:
        scan = f.to_scan_result()
        score = compute_confidence(scan)
        pred_positive = score >= threshold
        gt_positive = f.label in ("tp", "fn")
        gt_negative = f.label in ("tn", "fp")
        if pred_positive and gt_positive:
            tp += 1
        elif pred_positive and gt_negative:
            fp += 1
        elif not pred_positive and gt_negative:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall, tp, fp, tn, fn


def _fpr_at_threshold(
    fixtures: list[LabFixture],
    threshold: float,
) -> float:
    """FPR = FP / (TN + FP) over fixtures with label tn or fp (ground truth negative)."""
    neg = [f for f in fixtures if f.label in ("tn", "fp")]
    if not neg:
        return 0.0
    fp_count = 0
    for f in neg:
        score = compute_confidence(f.to_scan_result())
        if score >= threshold:
            fp_count += 1
    return fp_count / len(neg)


def _ece(fixtures: list[LabFixture], n_bins: int = 10) -> float:
    """Expected Calibrated Error: weighted sum of |mean_confidence - accuracy| per bin."""
    if len(fixtures) < MIN_LABELED_FOR_ECE:
        return 0.0
    scores: list[float] = []
    labels: list[bool] = []
    for f in fixtures:
        score = compute_confidence(f.to_scan_result())
        scores.append(score)
        labels.append(f.label in ("tp", "fn"))
    bin_edges = [i / n_bins for i in range(n_bins + 1)]
    ece = 0.0
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        in_bin = [j for j in range(len(scores)) if lo <= scores[j] < hi or (i == n_bins - 1 and scores[j] == hi)]
        if not in_bin:
            continue
        n = len(in_bin)
        mean_conf = sum(scores[j] for j in in_bin) / n
        accuracy = sum(1 for j in in_bin if labels[j]) / n
        ece += (n / len(scores)) * abs(mean_conf - accuracy)
    return ece


class TestPrecisionRecallMediumPlus(unittest.TestCase):
    """Precision and recall at threshold 0.45 (Medium+)."""

    def test_precision_recall_at_medium_plus(self):
        fixtures = _load_all_fixtures()
        labeled = _labeled_fixtures(fixtures)
        if len(labeled) < MIN_LABELED_FOR_METRICS:
            self.skipTest(
                f"Only {len(labeled)} labeled fixtures; need {MIN_LABELED_FOR_METRICS} for metrics",
            )
        precision, recall, tp, fp, tn, fn = _precision_recall_at_threshold(
            labeled, THRESHOLD_MEDIUM_PLUS,
        )
        self.assertGreaterEqual(
            precision, 0.0,
            f"Precision at 0.45 should be in [0,1], got {precision}",
        )
        self.assertLessEqual(precision, 1.0)
        self.assertGreaterEqual(recall, 0.0)
        self.assertLessEqual(recall, 1.0)
        if tp + fn > 0:
            self.assertGreater(
                recall, 0.0,
                f"At least one positive (tp/fn) fixture should be above threshold; tp={tp}, fn={fn}",
            )


class TestPrecisionRecallHigh(unittest.TestCase):
    """Precision and recall at threshold 0.75 (High)."""

    def test_precision_recall_at_high(self):
        fixtures = _load_all_fixtures()
        labeled = _labeled_fixtures(fixtures)
        if len(labeled) < MIN_LABELED_FOR_METRICS:
            self.skipTest(
                f"Only {len(labeled)} labeled fixtures; need {MIN_LABELED_FOR_METRICS} for metrics",
            )
        precision, recall, tp, fp, tn, fn = _precision_recall_at_threshold(
            labeled, THRESHOLD_HIGH,
        )
        self.assertGreaterEqual(precision, 0.0)
        self.assertLessEqual(precision, 1.0)
        self.assertGreaterEqual(recall, 0.0)
        self.assertLessEqual(recall, 1.0)


class TestFPR(unittest.TestCase):
    """False positive rate on negative (tn/fp) fixtures."""

    def test_fpr_below_lenient_max(self):
        fixtures = _load_all_fixtures()
        labeled = _labeled_fixtures(fixtures)
        neg = [f for f in labeled if f.label in ("tn", "fp")]
        if len(neg) < 1:
            self.skipTest("No negative (tn/fp) fixtures for FPR")
        fpr_medium = _fpr_at_threshold(labeled, THRESHOLD_MEDIUM_PLUS)
        fpr_high = _fpr_at_threshold(labeled, THRESHOLD_HIGH)
        self.assertLessEqual(
            fpr_medium, FPR_MAX_LENIENT,
            f"FPR at 0.45 should be <= {FPR_MAX_LENIENT}, got {fpr_medium}",
        )
        self.assertLessEqual(
            fpr_high, FPR_MAX_LENIENT,
            f"FPR at 0.75 should be <= {FPR_MAX_LENIENT}, got {fpr_high}",
        )


class TestECE(unittest.TestCase):
    """Expected Calibrated Error over labeled fixtures."""

    def test_ece_below_lenient_max(self):
        fixtures = _load_all_fixtures()
        labeled = _labeled_fixtures(fixtures)
        if len(labeled) < MIN_LABELED_FOR_ECE:
            self.skipTest(
                f"Only {len(labeled)} labeled fixtures; need {MIN_LABELED_FOR_ECE} for ECE",
            )
        ece = _ece(labeled, n_bins=10)
        self.assertLessEqual(
            ece, ECE_MAX_LENIENT,
            f"ECE should be <= {ECE_MAX_LENIENT}, got {ece:.4f}",
        )


if __name__ == "__main__":
    unittest.main()
