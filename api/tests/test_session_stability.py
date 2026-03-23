"""Detection stability tests: fixture-based session reports.

Verifies that canonical session fixtures produce deterministic session_verdict,
top_behavior_chains, and key_evidence. Any change to aggregation logic that
changes these outputs requires an explicit fixture/expected update.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from api.core.session_aggregation import aggregate_events_into_sessions


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "stability"


def _load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def _events_from_fixture(data: dict) -> list[tuple[datetime, str, str | None, dict]]:
    events: list[tuple[datetime, str, str | None, dict]] = []
    for ev in data["events"]:
        observed_at = ev["observed_at"]
        if isinstance(observed_at, str) and observed_at.endswith("Z"):
            observed_at = observed_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(observed_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tool_name = ev.get("tool_name", "")
        endpoint_id = ev.get("endpoint_id")
        payload = ev.get("payload", ev)
        events.append((dt, tool_name, endpoint_id, payload))
    return events


@pytest.mark.parametrize("fixture_name", [
    "execution_chain_basic",
    "execution_chain_multi_file",
    "shell_fanout_only",
    "sensitive_change_outbound",
])
def test_stability_fixture_produces_deterministic_report(fixture_name: str) -> None:
    """Each stability fixture produces a session report with expected verdict and evidence."""
    data = _load_fixture(fixture_name)
    events = _events_from_fixture(data)
    assert events, f"Fixture {fixture_name} has no events"
    reports = aggregate_events_into_sessions(events)
    assert reports, f"Fixture {fixture_name} produced no session reports"
    report = reports[0]
    expected = data.get("expected", {})
    if "session_verdict" in expected:
        assert report.session_verdict == expected["session_verdict"], (
            f"Fixture {fixture_name}: expected session_verdict "
            f"{expected['session_verdict']}, got {report.session_verdict}"
        )
    if "top_behavior_chains_contains" in expected:
        chains = report.top_behavior_chains or []
        for token in expected["top_behavior_chains_contains"]:
            assert any(token in c for c in chains), (
                f"Fixture {fixture_name}: expected a chain containing {token!r}, got {chains}"
            )
    if "key_evidence_contains" in expected:
        evidence = report.key_evidence or []
        for fragment in expected["key_evidence_contains"]:
            assert any(fragment.lower() in (e or "").lower() for e in evidence), (
                f"Fixture {fixture_name}: expected key_evidence to contain {fragment!r}, got {evidence}"
            )


def test_stability_identical_events_produce_identical_reports() -> None:
    """Same fixture run twice produces identical report fields."""
    data = _load_fixture("execution_chain_basic")
    events = _events_from_fixture(data)
    reports1 = aggregate_events_into_sessions(events)
    reports2 = aggregate_events_into_sessions(events)
    assert len(reports1) == len(reports2)
    for r1, r2 in zip(reports1, reports2):
        assert r1.session_verdict == r2.session_verdict
        assert (r1.top_behavior_chains or []) == (r2.top_behavior_chains or [])
        assert (r1.key_evidence or []) == (r2.key_evidence or [])
