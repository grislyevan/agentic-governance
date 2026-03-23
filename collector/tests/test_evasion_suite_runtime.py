"""INIT-31 runtime suite: run each EvasionScenario with deterministic scanner inputs/mocks and assert detector outputs.

Run with: pytest collector/tests/test_evasion_suite_runtime.py -v
Writes evasion_metrics.json when EVASION_METRICS_OUTPUT is set or to evasion_metrics.json in cwd.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evasion_suite_scenarios import EVASION_SCENARIOS, EvasionScenario
from scanner.evasion import EvasionScanner
from scanner.base import ScanResult
from telemetry.event_store import EventStore, ProcessExecEvent

# Collected for metrics artifact (E1-03). Appended by each runtime scenario test.
_EVASION_RUNTIME_METRICS: list[dict] = []


def _detected_vectors_from_result(result: ScanResult) -> list[str]:
    """Extract list of detector vector IDs from scan result."""
    if not result.evidence_details or "evasion_findings" not in result.evidence_details:
        return []
    return [f["vector"] for f in result.evidence_details["evasion_findings"]]


def _assert_scenario_expectations(
    scenario: EvasionScenario,
    result: ScanResult,
) -> tuple[bool, list[str]]:
    """Assert expected_vectors and boost bounds; return (passed, list of failure reasons)."""
    failures: list[str] = []
    detected = _detected_vectors_from_result(result)
    boost = result.evasion_boost

    if scenario.expected_vectors:
        for v in scenario.expected_vectors:
            if v not in detected:
                failures.append(f"expected vector {v!r} not in detected {detected!r}")
    if scenario.expected_min_boost is not None and boost < scenario.expected_min_boost:
        failures.append(
            f"evasion_boost {boost} < expected_min_boost {scenario.expected_min_boost}"
        )
    if scenario.expected_max_boost is not None and boost > scenario.expected_max_boost:
        failures.append(
            f"evasion_boost {boost} > expected_max_boost {scenario.expected_max_boost}"
        )

    return (len(failures) == 0, failures)


def _run_e4_coauthored_by_fixture(scanner: EvasionScanner, tmp_path: Path) -> ScanResult:
    """Simulate E4-CoAuthoredBy: global commit-msg hook that strips Co-Authored-By."""
    hooks_dir = tmp_path / "global-hooks"
    hooks_dir.mkdir()
    commit_msg = hooks_dir / "commit-msg"
    commit_msg.write_text('#!/bin/sh\ngrep -v "Co-Authored-By" "$1" > tmp && mv tmp "$1"')

    with patch.object(scanner, "_get_git_config", return_value=str(hooks_dir)):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    return scanner.scan(verbose=False)


def _run_e1_binary_rename_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E1-binary-rename: process tree with renamed AI binary (E4-renamed-binary)."""
    ps_table = "456 1 cursor\n123 456 myapp\n"
    ps_aux = textwrap.dedent("""\
        USER  PID %CPU %MEM VSZ RSS TTY STAT START TIME COMMAND
        user  123  1.0  0.5 100 50 ? S 10:00 0:01 /usr/local/bin/myapp --flag claude-code-agent
    """)
    mock_table = MagicMock()
    mock_table.returncode = 0
    mock_table.stdout = ps_table
    mock_aux = MagicMock()
    mock_aux.returncode = 0
    mock_aux.stdout = ps_aux

    with patch.object(scanner, "_run_cmd", side_effect=[mock_table, mock_aux]):
        with patch.object(scanner, "_get_git_config", return_value=None):
            with patch.object(scanner, "_find_git_repos", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    return scanner.scan(verbose=False)


def _run_e2_container_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E2-container: no evasion indicators (container has no dedicated detector yet)."""
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    return scanner.scan(verbose=False)


def _run_e6_kill_loop_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E6-kill-loop: process events with repeated kill/pkill of agent."""
    store = EventStore(max_events=100, retention_seconds=400)
    now = datetime.now(timezone.utc)
    store.push_process(
        ProcessExecEvent(now, 100, 1, "bash", "kill -9 12345; detec-agent", source="polling")
    )
    store.push_process(
        ProcessExecEvent(now, 101, 1, "zsh", "pkill -f collector", source="polling")
    )
    scanner._event_store = store
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch("scanner.evasion._collector_config_paths", return_value=[]):
                        return scanner.scan(verbose=False, diagnostics_context={})


def _run_e6_single_kill_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E6-single-kill: one kill event (below threshold, no E6)."""
    store = EventStore(max_events=100, retention_seconds=400)
    now = datetime.now(timezone.utc)
    store.push_process(
        ProcessExecEvent(now, 100, 1, "bash", "pkill -f detec", source="polling")
    )
    scanner._event_store = store
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch("scanner.evasion._collector_config_paths", return_value=[]):
                        return scanner.scan(verbose=False, diagnostics_context={})


def _run_e7_api_url_stripped_fixture(scanner: EvasionScanner, tmp_path: Path) -> ScanResult:
    """Simulate E7-api-url-stripped: collector.json with api_url empty and api_key set."""
    config_path = tmp_path / "collector.json"
    config_path.write_text(json.dumps({"api_url": "", "api_key": "secret"}))
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch.object(scanner, "_check_agent_interruption_patterns", return_value=[]):
                        with patch("scanner.evasion._collector_config_paths", return_value=[config_path]):
                            return scanner.scan(verbose=False, diagnostics_context={})


def _run_e7_dry_run_with_api_fixture(scanner: EvasionScanner, tmp_path: Path) -> ScanResult:
    """Simulate E7-dry-run-with-api: collector.json with dry_run true and api_url set."""
    config_path = tmp_path / "collector.json"
    config_path.write_text(
        json.dumps({"dry_run": True, "api_url": "https://api.example.com"})
    )
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch.object(scanner, "_check_agent_interruption_patterns", return_value=[]):
                        with patch("scanner.evasion._collector_config_paths", return_value=[config_path]):
                            return scanner.scan(verbose=False, diagnostics_context={})


def _run_e8_drift_polling_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E8-drift-polling: capability_drift present and provider polling."""
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch.object(scanner, "_check_agent_interruption_patterns", return_value=[]):
                        with patch("scanner.evasion._collector_config_paths", return_value=[]):
                            return scanner.scan(
                                verbose=False,
                                diagnostics_context={
                                    "capability_drift": ["file_read"],
                                    "provider_name": "polling",
                                },
                            )


def _run_e8_no_drift_fixture(scanner: EvasionScanner) -> ScanResult:
    """Simulate E8-no-drift: polling with no capability drift (no E8)."""
    with patch.object(scanner, "_get_git_config", return_value=None):
        with patch.object(scanner, "_find_git_repos", return_value=[]):
            with patch.object(scanner, "_check_renamed_binaries", return_value=[]):
                with patch.object(scanner, "_check_cursor_settings", return_value=[]):
                    with patch.object(scanner, "_check_agent_interruption_patterns", return_value=[]):
                        with patch("scanner.evasion._collector_config_paths", return_value=[]):
                            return scanner.scan(
                                verbose=False,
                                diagnostics_context={
                                    "capability_drift": [],
                                    "provider_name": "polling",
                                },
                            )


def _run_scenario(scenario: EvasionScenario, tmp_path: Path) -> ScanResult:
    """Run scanner with fixture appropriate to scenario_id."""
    scanner = EvasionScanner()
    if scenario.evasion_scenario_id == "E4-CoAuthoredBy":
        return _run_e4_coauthored_by_fixture(scanner, tmp_path)
    if scenario.evasion_scenario_id == "E1-binary-rename":
        return _run_e1_binary_rename_fixture(scanner)
    if scenario.evasion_scenario_id == "E2-container":
        return _run_e2_container_fixture(scanner)
    if scenario.evasion_scenario_id == "E6-kill-loop":
        return _run_e6_kill_loop_fixture(scanner)
    if scenario.evasion_scenario_id == "E6-single-kill":
        return _run_e6_single_kill_fixture(scanner)
    if scenario.evasion_scenario_id == "E7-api-url-stripped":
        return _run_e7_api_url_stripped_fixture(scanner, tmp_path)
    if scenario.evasion_scenario_id == "E7-dry-run-with-api":
        return _run_e7_dry_run_with_api_fixture(scanner, tmp_path)
    if scenario.evasion_scenario_id == "E8-drift-polling":
        return _run_e8_drift_polling_fixture(scanner)
    if scenario.evasion_scenario_id == "E8-no-drift":
        return _run_e8_no_drift_fixture(scanner)
    # Generic: run full scan (no mocks). Use for future scenarios.
    return scanner.scan(verbose=False)


@pytest.mark.evasion
@pytest.mark.slow
class TestEvasionSuiteRuntime:
    """Runtime assertions: scenario fixtures produce expected detector outputs."""

    @pytest.mark.parametrize("scenario", EVASION_SCENARIOS, ids=lambda s: s.evasion_scenario_id)
    def test_scenario_detector_output(self, scenario: EvasionScenario, tmp_path: Path) -> None:
        """Run scenario fixture and assert expected_vectors and boost bounds when set."""
        result = _run_scenario(scenario, tmp_path)
        detected = _detected_vectors_from_result(result)
        passed, failures = _assert_scenario_expectations(scenario, result)

        _EVASION_RUNTIME_METRICS.append({
            "evasion_scenario_id": scenario.evasion_scenario_id,
            "evasion_category": scenario.evasion_category,
            "detected_vectors": detected,
            "evasion_boost": result.evasion_boost,
            "passed": passed,
            "failures": failures,
        })

        assert passed, "; ".join(failures)

    def test_z_evasion_runtime_writes_metrics_artifact(self) -> None:
        """E1-03: Write evasion metrics JSON for CI artifact."""
        out_path = os.environ.get("EVASION_METRICS_OUTPUT", "evasion_metrics.json")
        passed = sum(1 for m in _EVASION_RUNTIME_METRICS if m.get("passed"))
        total = len(_EVASION_RUNTIME_METRICS)
        detected_all: list[str] = []
        missed: list[str] = []
        for m in _EVASION_RUNTIME_METRICS:
            detected_all.extend(m.get("detected_vectors", []))
            if not m.get("passed"):
                sid = m.get("evasion_scenario_id")
                scenario = next((s for s in EVASION_SCENARIOS if s.evasion_scenario_id == sid), None)
                if scenario and getattr(scenario, "expected_vectors", None):
                    for v in scenario.expected_vectors:
                        if v not in m.get("detected_vectors", []):
                            missed.append(v)

        artifact = {
            "scenario_pass_count": passed,
            "scenario_total": total,
            "detected_vectors": list(dict.fromkeys(detected_all)),
            "missed_vectors": list(dict.fromkeys(missed)),
            "scenarios": _EVASION_RUNTIME_METRICS,
        }
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        # Ensure at least one scenario ran (parametrized tests run before this)
        assert total >= 1, "No runtime scenario results collected"
