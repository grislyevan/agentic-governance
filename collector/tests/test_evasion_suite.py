"""Evasion suite runner (INIT-31). Deterministic scenarios with R0–R3 outcomes.

Run with: pytest collector/tests/test_evasion_suite.py -v
Optional marker: pytest -m evasion (add to pytest.ini to run evasion suite on demand).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
_TESTS_DIR = str(Path(__file__).resolve().parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)

from evasion_suite_scenarios import EVASION_SCENARIOS, EvasionScenario


def _outcome_for_scenario(scenario: EvasionScenario) -> str:
    """Map scenario to expected outcome (R0–R3). Used for regression.

    In a full implementation this would run the action_sequence, collect
    detection/confidence/decision, and classify into R0–R3. Here we
    assert the scenario is well-formed and the expected_degradation_profile
    is one of R0..R3.
    """
    return scenario.expected_degradation_profile


@pytest.mark.evasion
@pytest.mark.slow
class TestEvasionSuite:
    """Evasion suite: scenario structure and regression for baseline scenarios."""

    @pytest.mark.parametrize("scenario", EVASION_SCENARIOS, ids=lambda s: s.evasion_scenario_id)
    def test_scenario_has_valid_degradation_profile(self, scenario: EvasionScenario) -> None:
        """Each scenario must declare R0, R1, R2, or R3."""
        assert scenario.expected_degradation_profile in ("R0", "R1", "R2", "R3")

    @pytest.mark.parametrize("scenario", EVASION_SCENARIOS, ids=lambda s: s.evasion_scenario_id)
    def test_scenario_has_required_fields(self, scenario: EvasionScenario) -> None:
        """Scenario schema: required fields present."""
        assert scenario.evasion_scenario_id
        assert scenario.tool_id
        assert scenario.tool_class in ("A", "B", "C", "D")
        assert scenario.evasion_category in ("E1", "E2", "E3", "E4", "E5")
        assert scenario.pass_fail_criteria

    def test_e4_coauthored_by_scenario_regression(self) -> None:
        """E4-CoAuthoredBy (LAB-RUN-EVASION-001) is in suite and expects R1."""
        e4 = next(s for s in EVASION_SCENARIOS if s.evasion_scenario_id == "E4-CoAuthoredBy")
        assert e4.evasion_category == "E4"
        outcome = _outcome_for_scenario(e4)
        assert outcome == "R1"

    def test_e1_binary_rename_scenario_present(self) -> None:
        """At least one E1 scenario for binary/entry-point regression."""
        e1 = [s for s in EVASION_SCENARIOS if s.evasion_category == "E1"]
        assert len(e1) >= 1

    def test_e2_container_scenario_present(self) -> None:
        """At least one E2 scenario for environment isolation (container/remote-dev) regression."""
        e2 = [s for s in EVASION_SCENARIOS if s.evasion_category == "E2"]
        assert len(e2) >= 1
