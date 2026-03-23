"""Integration tests for the collector's main.py scan pipeline.

Tests the full run_scan pipeline end-to-end with stubbed scanners and
a mock emitter, verifying:
  - Stage 1a: named scanners run and produce detections
  - Stage 1b: BehavioralScanner PID dedup
  - Stage 1c: EvasionScanner cross-cutting findings
  - Stage 2: confidence scoring, policy evaluation, event emission
  - Error handling: scanner exceptions are caught gracefully
"""

from __future__ import annotations

import argparse
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from engine.confidence import compute_confidence, classify_confidence
from engine.policy import evaluate_policy
from main import run_scan
from orchestrator import (
    EVENT_VERSION,
    _collect_scan_results,
    _process_detection,
    build_event,
)
from scanner.base import BaseScanner, LayerSignals, ScanResult
from telemetry.event_store import EventStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_args(**overrides: Any) -> argparse.Namespace:
    """Build an argparse.Namespace with sensible test defaults."""
    defaults = {
        "endpoint_id": "test-host",
        "actor_id": "test-user",
        "sensitivity": "Tier0",
        "output": "./test-results.ndjson",
        "dry_run": True,
        "verbose": False,
        "interval": 0,
        "api_url": None,
        "api_key": None,
        "report_all": True,
        "enforcement_posture": "passive",
        "auto_enforce_threshold": 0.75,
        "enforce": False,
        "telemetry_provider": "polling",
        "network_allowlist_path": None,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _make_scan_result(
    tool_name: str = "Claude Code",
    tool_class: str = "B",
    detected: bool = True,
    *,
    process: float = 0.0,
    file: float = 0.0,
    network: float = 0.0,
    identity: float = 0.0,
    behavior: float = 0.0,
    evasion_boost: float = 0.0,
    penalties: list[tuple[str, float]] | None = None,
    action_risk: str = "R1",
    action_type: str = "exec",
    evidence_details: dict[str, Any] | None = None,
    process_patterns: list[str] | None = None,
) -> ScanResult:
    return ScanResult(
        detected=detected,
        tool_name=tool_name,
        tool_class=tool_class,
        tool_version="1.0.0",
        signals=LayerSignals(
            process=process,
            file=file,
            network=network,
            identity=identity,
            behavior=behavior,
        ),
        penalties=penalties or [],
        evasion_boost=evasion_boost,
        action_risk=action_risk,
        action_type=action_type,
        action_summary=f"{tool_name} detected on endpoint",
        evidence_details=evidence_details or {},
        process_patterns=process_patterns or [],
    )


class StubScanner(BaseScanner):
    """A scanner that returns a predetermined ScanResult."""

    def __init__(
        self,
        name: str,
        cls: str,
        result: ScanResult | None = None,
        raise_on_scan: bool = False,
    ) -> None:
        super().__init__(event_store=None)
        self._name = name
        self._cls = cls
        self._result = result
        self._raise_on_scan = raise_on_scan

    @property
    def tool_name(self) -> str:
        return self._name

    @property
    def tool_class(self) -> str:
        return self._cls

    def scan(self, verbose: bool = False) -> ScanResult:
        if self._raise_on_scan:
            raise RuntimeError(f"Simulated failure in {self._name}")
        if self._result is not None:
            return self._result
        return ScanResult(detected=False, tool_name=self._name, tool_class=self._cls)


class MockEmitter:
    """Captures emitted events for assertions instead of writing to disk."""

    def __init__(self, *, fail_on_emit: bool = False) -> None:
        self.events: list[dict[str, Any]] = []
        self._fail = fail_on_emit
        self._emitted = 0
        self._failed = 0

    def emit(self, event: dict[str, Any]) -> bool:
        if self._fail:
            self._failed += 1
            return False
        self.events.append(event)
        self._emitted += 1
        return True

    @property
    def stats(self) -> dict[str, int]:
        return {"emitted": self._emitted, "failed": self._failed}


# Shared mock for the PollingProvider so run_scan doesn't hit psutil
def _mock_polling_provider():
    provider = MagicMock()
    provider.name = "polling"
    provider.start = MagicMock()
    provider.stop = MagicMock()
    provider.poll = MagicMock()
    return provider


# ---------------------------------------------------------------------------
# Tests: _collect_scan_results (Stage 1a)
# ---------------------------------------------------------------------------

class TestCollectScanResults:
    def test_no_detections_returns_empty(self):
        scanners = [
            StubScanner("Claude Code", "B"),
            StubScanner("Cursor", "A"),
        ]
        detected, names, failures = _collect_scan_results(scanners, verbose=False)
        assert detected == []
        assert names == set()
        assert failures == set()

    def test_single_detection(self):
        scan = _make_scan_result("Claude Code", "B", True, process=0.8, file=0.6)
        scanners = [StubScanner("Claude Code", "B", result=scan)]
        detected, names, failures = _collect_scan_results(scanners, verbose=False)
        assert len(detected) == 1
        assert "Claude Code" in names
        assert failures == set()

    def test_multiple_detections(self):
        scan_cc = _make_scan_result("Claude Code", "B", True, process=0.8)
        scan_ol = _make_scan_result("Ollama", "A", True, process=0.9, network=0.7)
        scanners = [
            StubScanner("Claude Code", "B", result=scan_cc),
            StubScanner("Ollama", "A", result=scan_ol),
        ]
        detected, names, failures = _collect_scan_results(scanners, verbose=False)
        assert len(detected) == 2
        assert names == {"Claude Code", "Ollama"}

    def test_scanner_exception_recorded_as_failure(self):
        scanners = [
            StubScanner("Failing Tool", "A", raise_on_scan=True),
            StubScanner("Claude Code", "B"),
        ]
        detected, names, failures = _collect_scan_results(scanners, verbose=False)
        assert detected == []
        assert "Failing Tool" in failures
        assert len(failures) == 1


# ---------------------------------------------------------------------------
# Tests: build_event
# ---------------------------------------------------------------------------

class TestBuildEvent:
    def test_event_structure(self):
        scan = _make_scan_result("Claude Code", "B", True, process=0.8, file=0.6)
        event = build_event(
            event_type="detection.observed",
            endpoint_id="test-host",
            actor_id="test-user",
            session_id="sess-123",
            trace_id="trace-123",
            scan=scan,
            confidence=0.55,
            sensitivity="Tier1",
        )
        assert event["event_type"] == "detection.observed"
        assert event["event_version"] == EVENT_VERSION
        assert event["session_id"] == "sess-123"
        assert event["endpoint"]["id"] == "test-host"
        assert event["actor"]["id"] == "test-user"
        assert event["tool"]["name"] == "Claude Code"
        assert event["tool"]["attribution_confidence"] == 0.55
        assert event["target"]["sensitivity_tier"] == "Tier1"
        assert "event_id" in event
        assert "observed_at" in event

    def test_policy_included_when_provided(self):
        from engine.policy import PolicyDecision

        scan = _make_scan_result("Cursor", "A", True, process=0.5)
        decision = PolicyDecision(
            decision_state="warn",
            rule_id="ENFORCE-002",
            rule_version="0.4.0",
            reason_codes=["medium_confidence"],
            decision_confidence=0.55,
        )
        event = build_event(
            event_type="policy.evaluated",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            scan=scan,
            confidence=0.55,
            sensitivity="Tier0",
            policy=decision,
        )
        assert "policy" in event
        assert event["policy"]["decision_state"] == "warn"
        assert event["policy"]["rule_id"] == "ENFORCE-002"


# ---------------------------------------------------------------------------
# Tests: _process_detection (Stage 2)
# ---------------------------------------------------------------------------

class TestProcessDetection:
    def test_emits_detection_and_policy_events(self):
        emitter = MockEmitter()
        scan = _make_scan_result("Claude Code", "B", True, process=0.8, file=0.6)
        count = _process_detection(
            scan,
            sensitivity="Tier0",
            endpoint_id="host",
            actor_id="user",
            session_id="s1",
            trace_id="t1",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        assert count == 2
        assert len(emitter.events) == 2
        assert emitter.events[0]["event_type"] == "detection.observed"
        assert emitter.events[1]["event_type"] == "policy.evaluated"

    def test_policy_event_references_detection_as_parent(self):
        emitter = MockEmitter()
        scan = _make_scan_result("Cursor", "A", True, process=0.6, file=0.5)
        _process_detection(
            scan,
            sensitivity="Tier0",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        detection_id = emitter.events[0]["event_id"]
        policy_parent = emitter.events[1]["parent_event_id"]
        assert policy_parent == detection_id

    def test_emitter_failure_returns_zero(self):
        emitter = MockEmitter(fail_on_emit=True)
        scan = _make_scan_result("Claude Code", "B", True, process=0.8)
        count = _process_detection(
            scan,
            sensitivity="Tier0",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        assert count == 0


# ---------------------------------------------------------------------------
# Tests: full run_scan pipeline
# ---------------------------------------------------------------------------

class TestRunScanCleanSystem:
    """No tools detected: pipeline produces no events."""

    def test_clean_scan(self):
        emitter = MockEmitter()
        args = _make_args()

        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            for m in [m1, m_cowork, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0
        assert emitter.events == []
        assert emitter.stats["emitted"] == 0


class TestRunScanSingleDetection:
    """One tool detected produces correct event structure."""

    def test_single_tool_detected(self):
        emitter = MockEmitter()
        args = _make_args()

        cc_scan = _make_scan_result(
            "Claude Code", "B", True,
            process=0.80, file=0.60, network=0.40, identity=0.30,
        )
        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.return_value = cc_scan
            for m in [m2, m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0
        assert len(emitter.events) == 2
        detection = emitter.events[0]
        assert detection["event_type"] == "detection.observed"
        assert detection["tool"]["name"] == "Claude Code"
        assert detection["tool"]["class"] == "B"
        assert 0.0 < detection["tool"]["attribution_confidence"] <= 1.0


class TestRunScanMultipleDetections:
    """Multiple tools detected: one event pair per tool."""

    def test_two_tools_produce_four_events(self):
        emitter = MockEmitter()
        args = _make_args()

        cc_scan = _make_scan_result(
            "Claude Code", "B", True, process=0.8, file=0.6,
        )
        ol_scan = _make_scan_result(
            "Ollama", "A", True, process=0.9, network=0.7, file=0.5,
        )
        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.return_value = cc_scan
            m2.return_value.tool_name = "Ollama"
            m2.return_value.scan.return_value = ol_scan
            for m in [m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0
        # 2 tools x (detection + policy) = 4 events
        assert len(emitter.events) == 4
        tool_names = {e["tool"]["name"] for e in emitter.events if e["event_type"] == "detection.observed"}
        assert tool_names == {"Claude Code", "Ollama"}


class TestCredibilityGating:
    """Weak (low-confidence or no-signals) detections are suppressed; strong ones still emit."""

    def test_weak_and_strong_only_strong_emits(self):
        """One weak scan (low confidence) and one strong: only strong produces events."""
        emitter = MockEmitter()
        args = _make_args()

        weak_scan = _make_scan_result(
            "WeakTool", "A", True,
            process=0.0, file=0.0, network=0.0, identity=0.4, behavior=0.0,
        )
        weak_scan.action_summary = "No WeakTool signals detected"

        strong_scan = _make_scan_result(
            "Claude Code", "B", True,
            process=0.80, file=0.60, network=0.40, identity=0.30,
        )

        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.MCPScanner") as m_mcp,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.return_value = strong_scan
            m2.return_value.tool_name = "WeakTool"
            m2.return_value.scan.return_value = weak_scan
            for m in [m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected
            m_mcp.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0
        # Only strong tool (Claude Code) should emit; weak suppressed
        assert len(emitter.events) == 2
        detection = emitter.events[0]
        assert detection["event_type"] == "detection.observed"
        assert detection["tool"]["name"] == "Claude Code"
        assert detection["tool"]["attribution_confidence"] >= 0.20


class TestBehavioralScannerPidDedup:
    """BehavioralScanner receives PIDs from named scanners as exclude_pids."""

    def test_named_pids_excluded(self):
        emitter = MockEmitter()
        args = _make_args()

        cc_scan = _make_scan_result(
            "Claude Code", "B", True, process=0.8,
            evidence_details={
                "process_entries": [{"pid": 1234, "name": "claude"}],
            },
        )
        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        captured_exclude_pids = {}

        def capture_behavioral(*_args, **kwargs):
            captured_exclude_pids["pids"] = kwargs.get("exclude_pids", set())
            inst = MagicMock()
            inst.scan.return_value = not_detected
            return inst

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner", side_effect=capture_behavioral),
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.return_value = cc_scan
            for m in [m2, m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_ev.return_value.scan.return_value = not_detected

            run_scan(args, emitter=emitter)

        assert 1234 in captured_exclude_pids["pids"]


class TestEvasionBoost:
    """EvasionScanner findings add evasion_boost to results."""

    def test_evasion_scan_included_in_pipeline(self):
        emitter = MockEmitter()
        args = _make_args()

        evasion_scan = _make_scan_result(
            "Evasion Detection", "A", True,
            behavior=0.8, evasion_boost=0.15,
            evidence_details={
                "evasion_findings": [
                    {"vector": "E1-global-hook", "detail": "hook", "boost": 0.15},
                ],
            },
        )
        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            for m in [m1, m_cowork, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = evasion_scan

            run_scan(args, emitter=emitter)

        evasion_events = [
            e for e in emitter.events
            if e["tool"]["name"] == "Evasion Detection"
        ]
        assert len(evasion_events) >= 1
        confidence = evasion_events[0]["tool"]["attribution_confidence"]
        # The evasion boost should have raised confidence above the base score
        base_only = compute_confidence(
            _make_scan_result("Evasion Detection", "A", True, behavior=0.8)
        )
        boosted = compute_confidence(evasion_scan)
        assert boosted > base_only


class TestScannerFailureGraceful:
    """Scanner exceptions are caught gracefully and don't crash the pipeline."""

    def test_failing_scanner_does_not_crash(self):
        emitter = MockEmitter()
        args = _make_args()

        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            # First scanner throws
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.side_effect = RuntimeError("boom")
            for m in [m2, m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0

    def test_behavioral_scanner_failure_graceful(self):
        emitter = MockEmitter()
        args = _make_args()

        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            for m in [m1, m_cowork, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.side_effect = RuntimeError("behavioral boom")
            m_ev.return_value.scan.return_value = not_detected

            rc = run_scan(args, emitter=emitter)

        assert rc == 0

    def test_evasion_scanner_failure_graceful(self):
        emitter = MockEmitter()
        args = _make_args()

        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            for m in [m1, m_cowork, m2, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.side_effect = RuntimeError("evasion boom")

            rc = run_scan(args, emitter=emitter)

        assert rc == 0


class TestPolicyEvaluation:
    """Policy evaluation applies correct decision based on sensitivity level."""

    def test_low_confidence_tier0_detects(self):
        scan = _make_scan_result(
            "Claude Code", "B", True, process=0.3, file=0.2,
        )
        confidence = compute_confidence(scan)
        conf_class = classify_confidence(confidence)
        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class="B",
            sensitivity="Tier0",
            action_risk="R1",
        )
        assert decision.decision_state == "detect"

    def test_high_confidence_tier2_r3_requires_approval(self):
        scan = _make_scan_result(
            "Open Interpreter", "C", True,
            process=0.9, file=0.8, network=0.7, identity=0.6, behavior=0.9,
        )
        confidence = compute_confidence(scan)
        conf_class = classify_confidence(confidence)
        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class="C",
            sensitivity="Tier2",
            action_risk="R3",
        )
        assert decision.decision_state in ("approval_required", "block")

    def test_class_d_always_warns_minimum(self):
        scan = _make_scan_result(
            "OpenClaw", "D", True, process=0.3,
        )
        confidence = compute_confidence(scan)
        conf_class = classify_confidence(confidence)
        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class="D",
            sensitivity="Tier0",
            action_risk="R1",
        )
        # Class D always gets at least "warn" (ENFORCE-D03)
        assert decision.decision_state in ("warn", "approval_required", "block")

    def test_sensitivity_tier3_with_high_confidence_blocks(self):
        decision = evaluate_policy(
            confidence=0.85,
            confidence_class="High",
            tool_class="A",
            sensitivity="Tier3",
            action_risk="R4",
        )
        assert decision.decision_state == "block"

    def test_policy_decision_in_pipeline_event(self):
        emitter = MockEmitter()
        scan = _make_scan_result(
            "Claude Code", "B", True,
            process=0.9, file=0.8, network=0.6, identity=0.5, behavior=0.7,
        )
        _process_detection(
            scan,
            sensitivity="Tier2",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        policy_event = emitter.events[1]
        assert "policy" in policy_event
        assert policy_event["policy"]["decision_state"] in (
            "detect", "warn", "approval_required", "block",
        )
        assert policy_event["policy"]["rule_version"] == "0.4.0"


class TestConfidenceScoring:
    """Confidence scoring produces values in expected bands."""

    def test_zero_signals_produce_zero_confidence(self):
        scan = _make_scan_result("Claude Code", "B", True)
        confidence = compute_confidence(scan)
        assert confidence == 0.0

    def test_strong_signals_produce_high_confidence(self):
        scan = _make_scan_result(
            "Claude Code", "B", True,
            process=1.0, file=1.0, network=1.0, identity=1.0, behavior=1.0,
        )
        confidence = compute_confidence(scan)
        assert confidence >= 0.75
        assert classify_confidence(confidence) == "High"

    def test_moderate_signals_produce_medium_confidence(self):
        scan = _make_scan_result(
            "Claude Code", "B", True,
            process=0.8, file=0.7, network=0.5, identity=0.4, behavior=0.3,
        )
        confidence = compute_confidence(scan)
        assert 0.45 <= confidence < 0.75
        assert classify_confidence(confidence) == "Medium"

    def test_penalties_reduce_confidence(self):
        scan_no_penalty = _make_scan_result(
            "Claude Code", "B", True, process=0.8, file=0.6,
        )
        scan_with_penalty = _make_scan_result(
            "Claude Code", "B", True, process=0.8, file=0.6,
            penalties=[("weak_identity_correlation", 0.10)],
        )
        c_no = compute_confidence(scan_no_penalty)
        c_with = compute_confidence(scan_with_penalty)
        assert c_with < c_no

    def test_evasion_boost_increases_confidence(self):
        scan_no_boost = _make_scan_result(
            "Claude Code", "B", True, process=0.5, file=0.4,
        )
        scan_boosted = _make_scan_result(
            "Claude Code", "B", True, process=0.5, file=0.4,
            evasion_boost=0.15,
        )
        c_no = compute_confidence(scan_no_boost)
        c_boost = compute_confidence(scan_boosted)
        assert c_boost > c_no

    def test_confidence_clamped_to_unit_interval(self):
        scan = _make_scan_result(
            "Claude Code", "B", True,
            process=1.0, file=1.0, network=1.0, identity=1.0, behavior=1.0,
            evasion_boost=0.50,
        )
        confidence = compute_confidence(scan)
        assert 0.0 <= confidence <= 1.0

    def test_tool_specific_weights_used(self):
        scan_ollama = _make_scan_result(
            "Ollama", "A", True, process=0.8, network=0.8,
        )
        scan_default = _make_scan_result(
            "SomeUnknownTool", "A", True, process=0.8, network=0.8,
        )
        c_ollama = compute_confidence(scan_ollama)
        c_default = compute_confidence(scan_default)
        # Ollama weights network higher (0.25 vs 0.15), process lower (0.25 vs 0.30)
        assert c_ollama != c_default


class TestSeverityComputation:
    """Severity levels are correctly derived from confidence/risk/sensitivity."""

    def test_low_confidence_gets_s0(self):
        scan = _make_scan_result("Claude Code", "B", True, process=0.2)
        event = build_event(
            event_type="detection.observed",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            scan=scan,
            confidence=0.2,
            sensitivity="Tier0",
        )
        assert event["severity"]["level"] == "S0"

    def test_medium_confidence_gets_s1(self):
        scan = _make_scan_result("Claude Code", "B", True, process=0.7, file=0.5)
        event = build_event(
            event_type="detection.observed",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            scan=scan,
            confidence=0.55,
            sensitivity="Tier0",
        )
        assert event["severity"]["level"] == "S1"


class TestRunScanEventVersioning:
    """Events include correct version metadata."""

    def test_event_version_matches_module_constant(self):
        emitter = MockEmitter()
        args = _make_args()

        cc_scan = _make_scan_result("Claude Code", "B", True, process=0.8, file=0.6)
        not_detected = ScanResult(detected=False, tool_name="x")
        mock_provider = _mock_polling_provider()

        with (
            patch("orchestrator.get_best_provider", return_value=mock_provider),
            patch("orchestrator.ClaudeCodeScanner") as m1,
            patch("orchestrator.ClaudeCoworkScanner") as m_cowork,
            patch("orchestrator.OllamaScanner") as m2,
            patch("orchestrator.CursorScanner") as m3,
            patch("orchestrator.CopilotScanner") as m4,
            patch("orchestrator.OpenInterpreterScanner") as m5,
            patch("orchestrator.OpenClawScanner") as m6,
            patch("orchestrator.AiderScanner") as m7,
            patch("orchestrator.LMStudioScanner") as m8,
            patch("orchestrator.ContinueScanner") as m9,
            patch("orchestrator.GPTPilotScanner") as m10,
            patch("orchestrator.ClineScanner") as m11,
            patch("orchestrator.AIExtensionScanner") as m12,
            patch("orchestrator.BehavioralScanner") as m_beh,
            patch("orchestrator.EvasionScanner") as m_ev,
            patch("orchestrator.get_scheduler_evidence_by_tool", return_value={}),
        ):
            m1.return_value.tool_name = "Claude Code"
            m1.return_value.scan.return_value = cc_scan
            for m in [m2, m_cowork, m3, m4, m5, m6, m7, m8, m9, m10, m11, m12]:
                inst = m.return_value
                inst.tool_name = "stub"
                inst.scan.return_value = not_detected

            m_beh.return_value.scan.return_value = not_detected
            m_ev.return_value.scan.return_value = not_detected

            run_scan(args, emitter=emitter)

        for event in emitter.events:
            assert event["event_version"] == EVENT_VERSION


class TestMitreAttackMapping:
    """Events include MITRE ATT&CK mapping when applicable."""

    def test_detection_may_include_mitre(self):
        scan = _make_scan_result(
            "Claude Code", "B", True,
            process=0.8, file=0.6, behavior=0.5,
        )
        event = build_event(
            event_type="detection.observed",
            endpoint_id="host",
            actor_id="user",
            session_id="s",
            trace_id="t",
            scan=scan,
            confidence=0.65,
            sensitivity="Tier1",
        )
        # MITRE mapping is present when applicable (tool class B has mappings)
        if "mitre_attack" in event:
            assert isinstance(event["mitre_attack"]["techniques"], list)
