"""Evasion suite scenario definitions (INIT-31 schema).

Each scenario has: evasion_scenario_id, tool_id, tool_class, evasion_category,
expected_degradation_profile (R0–R3), pass_fail_criteria. Used by test_evasion_suite.py
and test_evasion_suite_runtime.py. Optional expected_vectors, expected_min_boost,
expected_max_boost drive runtime detector assertions when present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvasionScenario:
    evasion_scenario_id: str
    matrix_cell_id: str | None
    tool_id: str
    tool_class: str
    evasion_category: str  # E1..E5 (E6–E8 in Sprint E2)
    attack_technique_description: str
    preconditions: list[str]
    action_sequence: list[str]
    expected_degradation_profile: str  # R0, R1, R2, R3
    expected_policy_behavior: str
    required_evidence_outputs: list[str]
    pass_fail_criteria: dict[str, Any]
    # Optional detector outputs for runtime suite (INIT-31-E1-02). When set, runtime asserts.
    expected_vectors: list[str] = field(default_factory=list)  # scanner vector IDs (e.g. E1-global-hook)
    expected_min_boost: float | None = None  # inclusive lower bound for evasion_boost
    expected_max_boost: float | None = None  # inclusive upper bound for evasion_boost


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
        expected_vectors=["E1-global-hook"],
        expected_min_boost=0.15,
        expected_max_boost=0.50,
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
        expected_vectors=["E4-renamed-binary"],
        expected_min_boost=0.08,
        expected_max_boost=0.50,
    ),
    EvasionScenario(
        evasion_scenario_id="E2-container",
        matrix_cell_id=None,
        tool_id="Claude Code",
        tool_class="C",
        evasion_category="E2",
        attack_technique_description="Tool runs inside Docker or DevContainer; host telemetry has partial visibility",
        preconditions=["Tool installed", "Docker or DevContainer environment"],
        action_sequence=["Run tool inside container; agent on host or in same container observes process/file gap"],
        expected_degradation_profile="R1",
        expected_policy_behavior="Process/file layers may weaken; network/behavior and container context still apply.",
        required_evidence_outputs=["detection_assertion", "evidence_assertion"],
        pass_fail_criteria={
            "detection_assertion": "System still detects or classifies uncertainty",
            "evidence_assertion": "Minimum evidence set preserved; container context reported when available",
        },
        expected_vectors=[],
        expected_max_boost=0.0,
    ),
    # E6: Agent disable/kill loop (Sprint E2).
    EvasionScenario(
        evasion_scenario_id="E6-kill-loop",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E6",
        attack_technique_description="Repeated kill/pkill of collector process to suppress reporting",
        preconditions=["Agent running", "Process telemetry available"],
        action_sequence=["Run script or loop that kills detec-agent or collector process multiple times"],
        expected_degradation_profile="R1",
        expected_policy_behavior="Evasion scanner emits E6-agent-kill-loop; confidence boost applied.",
        required_evidence_outputs=["evasion_assertion"],
        pass_fail_criteria={
            "evasion_assertion": "E6-agent-kill-loop vector emitted when kill events exceed threshold",
        },
        expected_vectors=["E6-agent-kill-loop"],
        expected_min_boost=0.12,
        expected_max_boost=0.50,
    ),
    EvasionScenario(
        evasion_scenario_id="E6-single-kill",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E6",
        attack_technique_description="Single agent kill (below loop threshold)",
        preconditions=["Agent running", "Process telemetry available"],
        action_sequence=["Kill collector process once"],
        expected_degradation_profile="R0",
        expected_policy_behavior="E6 not emitted; single kill below threshold.",
        required_evidence_outputs=[],
        pass_fail_criteria={"evasion_assertion": "E6-agent-kill-loop not emitted for single event"},
        expected_vectors=[],
        expected_max_boost=0.0,
    ),
    # E7: Config tamper / policy suppression (Sprint E2).
    EvasionScenario(
        evasion_scenario_id="E7-api-url-stripped",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E7",
        attack_technique_description="Collector config edited to empty api_url with api_key set (reporting suppressed)",
        preconditions=["Collector config file writable"],
        action_sequence=["Set api_url to empty string while keeping api_key in collector.json"],
        expected_degradation_profile="R1",
        expected_policy_behavior="E7-config-tamper emitted; evasion boost applied.",
        required_evidence_outputs=["evasion_assertion"],
        pass_fail_criteria={"evasion_assertion": "E7-config-tamper vector emitted"},
        expected_vectors=["E7-config-tamper"],
        expected_min_boost=0.10,
        expected_max_boost=0.50,
    ),
    EvasionScenario(
        evasion_scenario_id="E7-dry-run-with-api",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E7",
        attack_technique_description="Config forces dry_run with api_url set (suppresses real reporting)",
        preconditions=["Collector config file writable"],
        action_sequence=["Set dry_run true and api_url in collector.json"],
        expected_degradation_profile="R1",
        expected_policy_behavior="E7-config-tamper emitted.",
        required_evidence_outputs=["evasion_assertion"],
        pass_fail_criteria={"evasion_assertion": "E7-config-tamper vector emitted"},
        expected_vectors=["E7-config-tamper"],
        expected_min_boost=0.10,
        expected_max_boost=0.50,
    ),
    # E8: Telemetry shaping (Sprint E2).
    EvasionScenario(
        evasion_scenario_id="E8-drift-polling",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E8",
        attack_technique_description="Telemetry capability drift while on polling (intentional downgrade inferred)",
        preconditions=["Provider is polling", "Capability drift present"],
        action_sequence=["Cause capability loss (e.g. disable native provider); agent runs on polling with drift"],
        expected_degradation_profile="R1",
        expected_policy_behavior="E8-telemetry-shaping emitted; evasion boost applied.",
        required_evidence_outputs=["evasion_assertion"],
        pass_fail_criteria={"evasion_assertion": "E8-telemetry-shaping vector emitted"},
        expected_vectors=["E8-telemetry-shaping"],
        expected_min_boost=0.10,
        expected_max_boost=0.50,
    ),
    EvasionScenario(
        evasion_scenario_id="E8-no-drift",
        matrix_cell_id=None,
        tool_id="Detec Agent",
        tool_class="X",
        evasion_category="E8",
        attack_technique_description="Polling provider with no capability drift (no E8)",
        preconditions=["Provider is polling", "No capability drift"],
        action_sequence=["Run agent on polling without any drift"],
        expected_degradation_profile="R0",
        expected_policy_behavior="E8 not emitted.",
        required_evidence_outputs=[],
        pass_fail_criteria={"evasion_assertion": "E8-telemetry-shaping not emitted"},
        expected_vectors=[],
        expected_max_boost=0.0,
    ),
]
