"""Evasion suite scenario definitions (INIT-31 schema).

Each scenario has: evasion_scenario_id, tool_id, tool_class, evasion_category,
expected_degradation_profile (R0–R3), pass_fail_criteria. Used by test_evasion_suite.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvasionScenario:
    evasion_scenario_id: str
    matrix_cell_id: str | None
    tool_id: str
    tool_class: str
    evasion_category: str  # E1..E5
    attack_technique_description: str
    preconditions: list[str]
    action_sequence: list[str]
    expected_degradation_profile: str  # R0, R1, R2, R3
    expected_policy_behavior: str
    required_evidence_outputs: list[str]
    pass_fail_criteria: dict[str, Any]


# Baseline scenarios for regression. E4-CoAuthoredBy from LAB-RUN-EVASION-001.
EVASION_SCENARIOS: list[EvasionScenario] = [
    EvasionScenario(
        evasion_scenario_id="E4-CoAuthoredBy",
        matrix_cell_id="CC-EVA-01",
        tool_id="Claude Code",
        tool_class="C",
        evasion_category="E4",
        attack_technique_description="Co-Authored-By git trailer suppression (settings, amend, or hook)",
        preconditions=["Claude Code installed", "git repo"],
        action_sequence=["Suppress trailer via settings or post-commit amend or global hook"],
        expected_degradation_profile="R1",
        expected_policy_behavior="Detection may rely on other layers; confidence can drop when trailer absent.",
        required_evidence_outputs=["detection_assertion", "confidence_assertion"],
        pass_fail_criteria={
            "detection_assertion": "System still detects or classifies uncertainty",
            "confidence_assertion": "Score reflects degraded certainty when trailer absent",
        },
    ),
    EvasionScenario(
        evasion_scenario_id="E1-binary-rename",
        matrix_cell_id=None,
        tool_id="Claude Code",
        tool_class="C",
        evasion_category="E1",
        attack_technique_description="Renamed or wrapped binary to avoid process-name attribution",
        preconditions=["Tool installed", "Binary renamed or launched via wrapper"],
        action_sequence=["Launch tool via wrapper/alias so process name is generic"],
        expected_degradation_profile="R1",
        expected_policy_behavior="Process layer may weaken; file/network/behavior layers still apply.",
        required_evidence_outputs=["detection_assertion", "evidence_assertion"],
        pass_fail_criteria={
            "detection_assertion": "System still detects or classifies uncertainty",
            "evidence_assertion": "Minimum evidence set preserved",
        },
    ),
]
