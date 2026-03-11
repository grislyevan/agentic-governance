"""Calibration replay harness: validates confidence scores against lab-run fixtures.

Loads structured fixture files from collector/tests/fixtures/lab_runs/ and
replays each through compute_confidence() and classify_confidence(). Validates:

  1. Band assignment matches expected_band (primary assertion)
  2. Score falls within expected_score_range (tolerance check)
  3. Cross-tool score ordering is preserved (regression check)

Run: pytest collector/tests/test_calibration.py -v
"""

from __future__ import annotations

import json
import os
import unittest
from dataclasses import dataclass
from pathlib import Path

from engine.confidence import compute_confidence, classify_confidence
from scanner.base import LayerSignals, ScanResult

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "lab_runs"


@dataclass
class LabFixture:
    lab_run: str
    tool_name: str
    tool_version: str
    tool_class: str
    platform: str
    date: str
    signals: LayerSignals
    penalties: list[tuple[str, float]]
    evasion_boost: float
    expected_band: str
    expected_score_range: tuple[float, float]
    notes: str

    @classmethod
    def from_json(cls, path: Path) -> "LabFixture":
        with open(path) as f:
            data = json.load(f)
        return cls(
            lab_run=data["lab_run"],
            tool_name=data["tool_name"],
            tool_version=data["tool_version"],
            tool_class=data["tool_class"],
            platform=data["platform"],
            date=data["date"],
            signals=LayerSignals(
                process=data["signals"]["process"],
                file=data["signals"]["file"],
                network=data["signals"]["network"],
                identity=data["signals"]["identity"],
                behavior=data["signals"]["behavior"],
            ),
            penalties=[(p[0], p[1]) for p in data["penalties"]],
            evasion_boost=data.get("evasion_boost", 0.0),
            expected_band=data["expected_band"],
            expected_score_range=(
                data["expected_score_range"][0],
                data["expected_score_range"][1],
            ),
            notes=data.get("notes", ""),
        )

    def to_scan_result(self) -> ScanResult:
        return ScanResult(
            detected=True,
            tool_name=self.tool_name,
            tool_class=self.tool_class,
            tool_version=self.tool_version,
            signals=self.signals,
            penalties=list(self.penalties),
            evasion_boost=self.evasion_boost,
        )


def _load_all_fixtures() -> list[LabFixture]:
    """Discover and load all JSON fixtures from the lab_runs directory."""
    fixtures = []
    if not FIXTURE_DIR.is_dir():
        return fixtures
    for path in sorted(FIXTURE_DIR.glob("*.json")):
        fixtures.append(LabFixture.from_json(path))
    return fixtures


ALL_FIXTURES = _load_all_fixtures()


class TestFixturesExist(unittest.TestCase):
    """Verify that the fixture corpus is present and non-empty."""

    def test_fixtures_loaded(self):
        self.assertGreater(
            len(ALL_FIXTURES), 0,
            f"No fixtures found in {FIXTURE_DIR}",
        )

    def test_at_least_three_tools(self):
        tools = {f.tool_name for f in ALL_FIXTURES}
        self.assertGreaterEqual(
            len(tools), 3,
            "Fixture corpus should cover at least 3 distinct tools",
        )


class TestBandAssignment(unittest.TestCase):
    """Primary assertion: each fixture produces the expected confidence band."""

    def test_band_matches(self):
        for fixture in ALL_FIXTURES:
            with self.subTest(lab_run=fixture.lab_run, tool=fixture.tool_name):
                scan = fixture.to_scan_result()
                score = compute_confidence(scan)
                band = classify_confidence(score)
                self.assertEqual(
                    band,
                    fixture.expected_band,
                    f"{fixture.lab_run} ({fixture.tool_name}): "
                    f"expected band {fixture.expected_band}, "
                    f"got {band} (score={score:.4f})",
                )


class TestScoreRange(unittest.TestCase):
    """Tolerance check: each fixture's score falls within expected range."""

    def test_score_within_range(self):
        for fixture in ALL_FIXTURES:
            with self.subTest(lab_run=fixture.lab_run, tool=fixture.tool_name):
                scan = fixture.to_scan_result()
                score = compute_confidence(scan)
                lo, hi = fixture.expected_score_range
                self.assertGreaterEqual(
                    score, lo,
                    f"{fixture.lab_run} ({fixture.tool_name}): "
                    f"score {score:.4f} below range [{lo}, {hi}]",
                )
                self.assertLessEqual(
                    score, hi,
                    f"{fixture.lab_run} ({fixture.tool_name}): "
                    f"score {score:.4f} above range [{lo}, {hi}]",
                )


class TestScoreOrdering(unittest.TestCase):
    """Regression check: cross-tool score ordering is preserved.

    For every pair of fixtures where the expected score ranges do not
    overlap, the fixture with the higher range must still score higher
    with current weights. This catches weight changes that invert the
    relative ranking of tools.
    """

    def test_pairwise_ordering(self):
        for i, a in enumerate(ALL_FIXTURES):
            for b in ALL_FIXTURES[i + 1:]:
                a_lo, a_hi = a.expected_score_range
                b_lo, b_hi = b.expected_score_range

                # Skip pairs with overlapping ranges
                if a_lo <= b_hi and b_lo <= a_hi:
                    continue

                scan_a = a.to_scan_result()
                scan_b = b.to_scan_result()
                score_a = compute_confidence(scan_a)
                score_b = compute_confidence(scan_b)

                if a_lo > b_hi:
                    self.assertGreater(
                        score_a, score_b,
                        f"Ordering regression: {a.lab_run} ({a.tool_name}, "
                        f"score={score_a:.4f}) should outscore "
                        f"{b.lab_run} ({b.tool_name}, score={score_b:.4f})",
                    )
                elif b_lo > a_hi:
                    self.assertGreater(
                        score_b, score_a,
                        f"Ordering regression: {b.lab_run} ({b.tool_name}, "
                        f"score={score_b:.4f}) should outscore "
                        f"{a.lab_run} ({a.tool_name}, score={score_a:.4f})",
                    )


class TestInfrastructureFloor(unittest.TestCase):
    """Verify that the infrastructure floor applies correctly.

    LAB-RUN-013 (OpenClaw with local LLM) has process=0.85 and
    file=0.95, both above 0.80. The infrastructure floor should
    prevent the score from falling below 0.70 even though the
    behavior layer dropped to 0.40.
    """

    def test_openclaw_local_llm_floor(self):
        fixture = next(
            (f for f in ALL_FIXTURES if f.lab_run == "LAB-RUN-013"), None,
        )
        if fixture is None:
            self.skipTest("LAB-RUN-013 fixture not found")

        scan = fixture.to_scan_result()
        score = compute_confidence(scan)
        self.assertGreaterEqual(
            score, 0.70,
            f"Infrastructure floor should keep OpenClaw (local LLM) "
            f"at or above 0.70, got {score:.4f}",
        )


class TestWeightSumInvariant(unittest.TestCase):
    """Verify that per-tool weights sum to 1.0 for all tools in fixtures."""

    def test_weights_sum_to_one(self):
        from engine.confidence import get_weights

        seen: set[str] = set()
        for fixture in ALL_FIXTURES:
            if fixture.tool_name in seen:
                continue
            seen.add(fixture.tool_name)

            with self.subTest(tool=fixture.tool_name):
                weights = get_weights(fixture.tool_name)
                total = sum(weights.values())
                self.assertAlmostEqual(
                    total, 1.0, places=4,
                    msg=f"{fixture.tool_name} weights sum to {total}, expected 1.0",
                )


if __name__ == "__main__":
    unittest.main()
