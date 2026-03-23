"""Tests for capability drift detection."""

from __future__ import annotations

import pytest

from telemetry.capabilities import TelemetryCapabilities
from telemetry.capability_drift import check_drift, _reset_for_test


@pytest.fixture(autouse=True)
def _reset_drift_state() -> None:
    _reset_for_test()
    yield
    _reset_for_test()


def test_first_scan_no_drift() -> None:
    cap = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=True,
        has_file_read=True,
        has_network_events=True,
        has_process_parent=True,
    )
    assert check_drift(cap, debounce_scans=1) == []


def test_drift_after_capability_lost_debounce_one() -> None:
    full = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=True,
        has_file_read=True,
        has_network_events=True,
        has_process_parent=True,
    )
    reduced = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=False,
        has_file_read=False,
        has_network_events=True,
        has_process_parent=True,
    )
    check_drift(full, debounce_scans=1)
    drifted = check_drift(reduced, debounce_scans=1)
    assert set(drifted) == {"file_change", "file_read"}


def test_no_drift_when_capability_restored() -> None:
    full = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=True,
        has_file_read=True,
        has_network_events=True,
        has_process_parent=True,
    )
    reduced = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=False,
        has_file_read=False,
        has_network_events=True,
        has_process_parent=True,
    )
    check_drift(full, debounce_scans=1)
    check_drift(reduced, debounce_scans=1)
    restored = check_drift(full, debounce_scans=1)
    assert restored == []


def test_debounce_requires_consecutive_scans() -> None:
    full = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=True,
        has_file_read=True,
        has_network_events=True,
        has_process_parent=True,
    )
    reduced = TelemetryCapabilities(
        has_process_exec=True,
        has_file_change=False,
        has_file_read=False,
        has_network_events=True,
        has_process_parent=True,
    )
    check_drift(full, debounce_scans=2)
    assert check_drift(reduced, debounce_scans=2) == []
    assert set(check_drift(reduced, debounce_scans=2)) == {"file_change", "file_read"}
