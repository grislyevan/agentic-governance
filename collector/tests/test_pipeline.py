"""Integration tests for the scan-to-event pipeline (collector/main.py).

Covers:
  - build_event produces schema-valid events for all event types
  - _process_detection emits the correct chain of events
  - enforcement.applied includes both enforcement and outcome fields
  - parent_event_id linking across detection → policy → enforcement
  - _emit_cleared_events for tools that vanish between cycles
  - run_scan end-to-end with mocked scanners (dry-run, NDJSON, stats)
  - scanner failure handling (exceptions don't crash the pipeline)
  - HttpEmitter stats interface compatibility
"""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from main import run_scan
from orchestrator import (
    build_event,
    _collect_scan_results,
    _emit_cleared_events,
    _process_detection,
)
from scanner.base import ScanResult, LayerSignals
from engine.policy import PolicyDecision
from enforcement.enforcer import Enforcer, EnforcementResult
from schema.validator import EventValidator
from output.emitter import EventEmitter
from output.http_emitter import HttpEmitter
from agent.state import StateDiffer


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _validator() -> EventValidator:
    return EventValidator(schema_path=_repo_root() / "schemas" / "canonical-event-schema.json")


def _make_scan(
    tool_name: str = "TestTool",
    tool_class: str = "A",
    detected: bool = True,
    process: float = 0.8,
    file: float = 0.6,
) -> ScanResult:
    return ScanResult(
        detected=detected,
        tool_name=tool_name,
        tool_class=tool_class,
        tool_version="1.0.0",
        signals=LayerSignals(process=process, file=file, network=0.0, identity=0.5, behavior=0.0),
        action_summary=f"{tool_name} detected via process scan",
        action_type="exec",
        action_risk="R2",
    )


def _base_kwargs() -> dict:
    return {
        "endpoint_id": "TEST-EP-001",
        "actor_id": "tester@example.com",
        "session_id": "test-session-001",
        "trace_id": "trace-test-001",
        "sensitivity": "Tier0",
    }


class TestBuildEvent(unittest.TestCase):
    """build_event must produce schema-valid events for every event type."""

    def setUp(self) -> None:
        self.validator = _validator()
        self.scan = _make_scan()
        self.kwargs = _base_kwargs()

    def test_detection_observed_is_valid(self) -> None:
        event = build_event(
            event_type="detection.observed",
            scan=self.scan,
            confidence=0.75,
            **self.kwargs,
        )
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"detection.observed failed: {errors}")
        self.assertEqual(event["event_type"], "detection.observed")
        self.assertIn("tool", event)
        self.assertIn("action", event)
        self.assertIn("target", event)

    def test_policy_evaluated_is_valid(self) -> None:
        policy = PolicyDecision(
            decision_state="warn",
            rule_id="TEST-001",
            rule_version="1.0.0",
            reason_codes=["test_reason"],
            decision_confidence=0.8,
        )
        event = build_event(
            event_type="policy.evaluated",
            scan=self.scan,
            confidence=0.75,
            parent_event_id="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
            policy=policy,
            **self.kwargs,
        )
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"policy.evaluated failed: {errors}")
        self.assertEqual(event["policy"]["decision_state"], "warn")
        self.assertEqual(event["parent_event_id"], "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d")

    def test_enforcement_applied_is_valid(self) -> None:
        policy = PolicyDecision(
            decision_state="block",
            rule_id="TEST-002",
            rule_version="1.0.0",
            reason_codes=["blocked"],
            decision_confidence=0.9,
        )
        enforcement = EnforcementResult(
            tactic="kill_process",
            success=True,
            detail="Process terminated",
            simulated=False,
            allow_listed=False,
        )
        event = build_event(
            event_type="enforcement.applied",
            scan=self.scan,
            confidence=0.85,
            parent_event_id="b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
            policy=policy,
            enforcement=enforcement,
            **self.kwargs,
        )
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"enforcement.applied failed: {errors}")
        self.assertEqual(event["enforcement"]["tactic"], "kill_process")
        self.assertTrue(event["enforcement"]["success"])
        self.assertEqual(event["outcome"]["enforcement_result"], "denied")
        self.assertFalse(event["outcome"]["incident_flag"])

    def test_enforcement_failed_maps_to_allowed(self) -> None:
        policy = PolicyDecision(
            decision_state="block",
            rule_id="TEST-002",
            rule_version="1.0.0",
            reason_codes=["blocked"],
            decision_confidence=0.9,
        )
        enforcement = EnforcementResult(
            tactic="kill_process",
            success=False,
            detail="Process not found",
            simulated=False,
            allow_listed=False,
        )
        event = build_event(
            event_type="enforcement.applied",
            scan=self.scan,
            confidence=0.85,
            policy=policy,
            enforcement=enforcement,
            **self.kwargs,
        )
        self.assertEqual(event["outcome"]["enforcement_result"], "allowed")

    def test_detection_cleared_is_valid(self) -> None:
        cleared_scan = ScanResult(
            detected=False,
            tool_name="TestTool",
            tool_class="A",
            action_type="removal",
            action_risk="R1",
            action_summary="TestTool is no longer detected on this endpoint",
        )
        event = build_event(
            event_type="detection.cleared",
            scan=cleared_scan,
            confidence=0.0,
            **self.kwargs,
        )
        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"detection.cleared failed: {errors}")

    def test_event_ids_are_unique(self) -> None:
        e1 = build_event("detection.observed", scan=self.scan, confidence=0.5, **self.kwargs)
        e2 = build_event("detection.observed", scan=self.scan, confidence=0.5, **self.kwargs)
        self.assertNotEqual(e1["event_id"], e2["event_id"])


class TestProcessDetection(unittest.TestCase):
    """_process_detection must emit the correct chain for each policy outcome."""

    def setUp(self) -> None:
        self.scan = _make_scan()
        self.validator = _validator()

    def _collect_emitted(self, emitter: MagicMock) -> list[dict]:
        return [call.args[0] for call in emitter.emit.call_args_list]

    def test_detect_emits_two_events(self) -> None:
        """A detect decision: detection.observed + policy.evaluated."""
        emitter = MagicMock()
        emitter.emit.return_value = True
        count = _process_detection(
            self.scan,
            sensitivity="Tier0",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        self.assertEqual(count, 2)
        events = self._collect_emitted(emitter)
        self.assertEqual(events[0]["event_type"], "detection.observed")
        self.assertEqual(events[1]["event_type"], "policy.evaluated")

    def test_parent_event_id_chain(self) -> None:
        """policy.evaluated must reference the detection event's ID as parent."""
        emitter = MagicMock()
        emitter.emit.return_value = True
        _process_detection(
            self.scan,
            sensitivity="Tier0",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=None,
            state_differ=None,
            verbose=False,
        )
        events = self._collect_emitted(emitter)
        det_id = events[0]["event_id"]
        self.assertEqual(events[1]["parent_event_id"], det_id)

    @patch("orchestrator.evaluate_policy")
    def test_block_emits_three_events(self, mock_policy: MagicMock) -> None:
        """A block decision with enforcement: 3 events total."""
        mock_policy.return_value = PolicyDecision(
            decision_state="block",
            rule_id="BLOCK-01",
            rule_version="1.0.0",
            reason_codes=["test_block"],
            decision_confidence=0.9,
        )
        enforcer = MagicMock(spec=Enforcer)
        enforcer.enforce.return_value = EnforcementResult(
            tactic="kill_process", success=True, detail="killed",
            simulated=False, allow_listed=False,
        )
        emitter = MagicMock()
        emitter.emit.return_value = True

        count = _process_detection(
            self.scan,
            sensitivity="Tier1",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=enforcer,
            state_differ=None,
            verbose=False,
        )
        self.assertEqual(count, 3)
        events = self._collect_emitted(emitter)
        self.assertEqual(events[2]["event_type"], "enforcement.applied")
        self.assertEqual(events[2]["parent_event_id"], events[1]["event_id"])

    @patch("orchestrator.evaluate_policy")
    def test_enforcement_events_pass_schema(self, mock_policy: MagicMock) -> None:
        """All three events from a block decision must pass schema validation."""
        mock_policy.return_value = PolicyDecision(
            decision_state="block",
            rule_id="BLOCK-01",
            rule_version="1.0.0",
            reason_codes=["test_block"],
            decision_confidence=0.9,
        )
        enforcer = MagicMock(spec=Enforcer)
        enforcer.enforce.return_value = EnforcementResult(
            tactic="kill_process", success=True, detail="killed",
            simulated=False, allow_listed=False,
        )
        emitter = MagicMock()
        emitter.emit.return_value = True

        _process_detection(
            self.scan,
            sensitivity="Tier1",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=enforcer,
            state_differ=None,
            verbose=False,
        )
        events = self._collect_emitted(emitter)
        for ev in events:
            errors = self.validator.validate(ev)
            self.assertEqual(errors, [], f"{ev['event_type']} failed: {errors}")

    @patch("orchestrator.evaluate_policy")
    def test_approval_required_does_not_kill(self, mock_policy: MagicMock) -> None:
        """approval_required must NOT trigger OS-level enforcement (M-28 fix).

        The enforcer IS called (it emits an enforcement event), but the
        tactic is hold_pending_approval, not process_kill or network_block.
        """
        mock_policy.return_value = PolicyDecision(
            decision_state="approval_required",
            rule_id="APPR-01",
            rule_version="1.0.0",
            reason_codes=["needs_approval"],
            decision_confidence=0.8,
        )
        enforcer = MagicMock(spec=Enforcer)
        enforcer.enforce.return_value = EnforcementResult(
            tactic="hold_pending_approval",
            success=True,
            detail="Holding test_tool pending approval",
            tool_name="test_tool",
            simulated=False,
            allow_listed=False,
        )
        emitter = MagicMock()
        emitter.emit.return_value = True

        count = _process_detection(
            self.scan,
            sensitivity="Tier1",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=enforcer,
            state_differ=None,
            verbose=False,
        )
        self.assertEqual(count, 3)
        enforcer.enforce.assert_called_once()
        result = enforcer.enforce.return_value
        self.assertEqual(result.tactic, "hold_pending_approval")

    def test_state_differ_skips_unchanged(self) -> None:
        """StateDiffer returning (False, []) must suppress all events."""
        differ = MagicMock(spec=StateDiffer)
        differ.is_changed.return_value = (False, [])
        emitter = MagicMock()
        emitter.emit.return_value = True

        count = _process_detection(
            self.scan,
            sensitivity="Tier0",
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            emitter=emitter,
            enforcer=None,
            state_differ=differ,
            verbose=False,
        )
        self.assertEqual(count, 0)
        emitter.emit.assert_not_called()


class TestClearedEvents(unittest.TestCase):
    """_emit_cleared_events must emit detection.cleared for vanished tools."""

    def test_cleared_tool_emits_event(self) -> None:
        differ = MagicMock(spec=StateDiffer)
        differ.cleared_tools.return_value = ["TestTool"]
        differ.get_last_class.return_value = "A"

        emitter = MagicMock()
        emitter.emit.return_value = True

        count = _emit_cleared_events(
            differ,
            detected_tools=set(),
            scan_failures=set(),
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            sensitivity="Tier0",
            emitter=emitter,
            verbose=False,
        )
        self.assertEqual(count, 1)
        event = emitter.emit.call_args[0][0]
        self.assertEqual(event["event_type"], "detection.cleared")
        self.assertEqual(event["tool"]["name"], "TestTool")
        differ.mark_cleared.assert_called_once_with("TestTool")

    def test_cleared_event_validates(self) -> None:
        differ = MagicMock(spec=StateDiffer)
        differ.cleared_tools.return_value = ["OllamaGone"]
        differ.get_last_class.return_value = "B"

        emitter = MagicMock()
        emitter.emit.return_value = True

        _emit_cleared_events(
            differ,
            detected_tools=set(),
            scan_failures=set(),
            endpoint_id="EP-01",
            actor_id="user@test",
            session_id="sess",
            trace_id="trace",
            sensitivity="Tier0",
            emitter=emitter,
            verbose=False,
        )
        event = emitter.emit.call_args[0][0]
        errors = _validator().validate(event)
        self.assertEqual(errors, [], f"detection.cleared failed: {errors}")


class TestCollectScanResults(unittest.TestCase):
    """_collect_scan_results must partition scanners into detections and failures."""

    def test_detected_scan_collected(self) -> None:
        scanner = MagicMock()
        scanner.tool_name = "MockTool"
        scanner.scan.return_value = _make_scan("MockTool")

        detected, names, failures = _collect_scan_results([scanner], verbose=False)
        self.assertEqual(len(detected), 1)
        self.assertIn("MockTool", names)
        self.assertEqual(len(failures), 0)

    def test_undetected_scan_skipped(self) -> None:
        scanner = MagicMock()
        scanner.tool_name = "GhostTool"
        scanner.scan.return_value = _make_scan("GhostTool", detected=False)

        detected, names, failures = _collect_scan_results([scanner], verbose=False)
        self.assertEqual(len(detected), 0)

    def test_scanner_exception_recorded_as_failure(self) -> None:
        scanner = MagicMock()
        scanner.tool_name = "CrashTool"
        scanner.scan.side_effect = RuntimeError("boom")

        detected, names, failures = _collect_scan_results([scanner], verbose=False)
        self.assertEqual(len(detected), 0)
        self.assertIn("CrashTool", failures)


class TestRunScanEndToEnd(unittest.TestCase):
    """run_scan end-to-end with mocked scanners."""

    def _make_args(self, **overrides) -> argparse.Namespace:
        defaults = {
            "endpoint_id": "EP-01",
            "actor_id": "user@test.com",
            "sensitivity": "Tier0",
            "verbose": False,
            "dry_run": True,
            "output": str(Path(tempfile.mkdtemp()) / "test-events.ndjson"),
            "enforce": False,
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    @patch("orchestrator.get_best_provider")
    @patch("orchestrator.MCPScanner")
    @patch("orchestrator.EvasionScanner")
    @patch("orchestrator.BehavioralScanner")
    @patch("orchestrator.AIExtensionScanner")
    @patch("orchestrator.ClineScanner")
    @patch("orchestrator.GPTPilotScanner")
    @patch("orchestrator.ContinueScanner")
    @patch("orchestrator.LMStudioScanner")
    @patch("orchestrator.AiderScanner")
    @patch("orchestrator.OpenClawScanner")
    @patch("orchestrator.OpenInterpreterScanner")
    @patch("orchestrator.CopilotScanner")
    @patch("orchestrator.CursorScanner")
    @patch("orchestrator.OllamaScanner")
    @patch("orchestrator.ClaudeCoworkScanner")
    @patch("orchestrator.ClaudeCodeScanner")
    def test_dry_run_no_detections(self, *mock_scanners: MagicMock) -> None:
        """Dry-run with no detections: zero events, exit code 0."""
        mock_provider = MagicMock()
        mock_provider.name = "polling"
        mock_provider.start = MagicMock()
        mock_provider.stop = MagicMock()
        mock_provider.poll = MagicMock()
        mock_scanners[-1].return_value = mock_provider  # get_best_provider (top decorator)
        for m in mock_scanners[:-1]:  # scanner mocks
            if hasattr(m.return_value, "scan"):
                instance = m.return_value
                instance.tool_name = "Mock"
                instance.scan.return_value = ScanResult(detected=False, tool_name="Mock")

        args = self._make_args()
        code = run_scan(args)
        self.assertEqual(code, 0)

    @patch("orchestrator.get_best_provider")
    @patch("orchestrator.MCPScanner")
    @patch("orchestrator.EvasionScanner")
    @patch("orchestrator.BehavioralScanner")
    @patch("orchestrator.AIExtensionScanner")
    @patch("orchestrator.ClineScanner")
    @patch("orchestrator.GPTPilotScanner")
    @patch("orchestrator.ContinueScanner")
    @patch("orchestrator.LMStudioScanner")
    @patch("orchestrator.AiderScanner")
    @patch("orchestrator.OpenClawScanner")
    @patch("orchestrator.OpenInterpreterScanner")
    @patch("orchestrator.CopilotScanner")
    @patch("orchestrator.CursorScanner")
    @patch("orchestrator.OllamaScanner")
    @patch("orchestrator.ClaudeCoworkScanner")
    @patch("orchestrator.ClaudeCodeScanner")
    def test_detection_writes_ndjson(self, *mock_scanners: MagicMock) -> None:
        """Single detection in NDJSON mode writes valid events."""
        mock_provider = MagicMock()
        mock_provider.name = "polling"
        mock_provider.start = MagicMock()
        mock_provider.stop = MagicMock()
        mock_provider.poll = MagicMock()
        mock_scanners[-1].return_value = mock_provider
        for m in mock_scanners[:-1]:
            if hasattr(m.return_value, "scan"):
                instance = m.return_value
                instance.tool_name = "NoTool"
                instance.scan.return_value = ScanResult(detected=False, tool_name="NoTool")

        mock_scanners[0].return_value.tool_name = "ClaudeCode"
        mock_scanners[0].return_value.scan.return_value = _make_scan("ClaudeCode", "C")

        with tempfile.NamedTemporaryFile(suffix=".ndjson", delete=False) as f:
            path = f.name
        try:
            args = self._make_args(dry_run=False, output=path)
            code = run_scan(args)
            self.assertEqual(code, 0)

            with open(path) as f:
                lines = [json.loads(line) for line in f if line.strip()]
            self.assertGreaterEqual(len(lines), 2)
            types = [e["event_type"] for e in lines]
            self.assertIn("detection.observed", types)
            self.assertIn("policy.evaluated", types)

            validator = _validator()
            for event in lines:
                errors = validator.validate(event)
                self.assertEqual(errors, [], f"{event['event_type']}: {errors}")
        finally:
            Path(path).unlink(missing_ok=True)


class TestHttpEmitterStatsCompat(unittest.TestCase):
    """HttpEmitter.stats must include 'emitted' and 'failed' keys."""

    def test_stats_has_emitted_and_failed(self) -> None:
        emitter = HttpEmitter.__new__(HttpEmitter)
        emitter._sent = 5
        emitter._buffered = 2
        emitter._buffer = MagicMock()
        emitter._buffer.size.return_value = 2

        stats = emitter.stats
        self.assertIn("emitted", stats)
        self.assertIn("failed", stats)
        self.assertEqual(stats["emitted"], 5)
        self.assertEqual(stats["failed"], 2)
        self.assertEqual(stats["sent"], 5)
        self.assertEqual(stats["buffered"], 2)


if __name__ == "__main__":
    unittest.main()
