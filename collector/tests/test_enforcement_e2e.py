"""End-to-end test: behavioral detection -> policy evaluation -> enforcement -> event emission.

Exercises the full detection-to-enforcement-to-audit path described in the
enforcement roadmap (Task 9). Runs without root/admin by mocking process kill
and network block operations.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from enforcement.enforcer import Enforcer, EnforcementResult
from enforcement.posture import PostureManager
from engine.confidence import classify_confidence, compute_confidence
from engine.policy import PolicyDecision, evaluate_policy
from main import build_event
from scanner.base import ScanResult
from scanner.behavioral import BehavioralScanner
from schema.validator import EventValidator
from telemetry.event_store import (
    EventStore,
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

_BASE = datetime(2026, 3, 12, 10, 0, 0, tzinfo=timezone.utc)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _validator() -> EventValidator:
    return EventValidator(schema_path=_repo_root() / "schemas" / "canonical-event-schema.json")


def _base_event_kwargs() -> dict:
    return {
        "endpoint_id": "E2E-EP-001",
        "actor_id": "e2e-test@detec.io",
        "session_id": "e2e-session-001",
        "trace_id": "e2e-trace-001",
        "sensitivity": "Tier1",
    }


def _seed_event_store() -> EventStore:
    """Seed an EventStore with synthetic events triggering multiple BEH patterns.

    Patterns triggered:
      BEH-001 (shell fan-out): 12 child shells within 60s (score ~1.0)
      BEH-002 (LLM API cadence): 10 LLM API connections within 120s (score ~1.0)
      BEH-003 (burst write): 15 files across 5 dirs within 30s
      BEH-004 (RMW loop): interleaved file/network events
      BEH-005 (session duration): activity spread over 15 minutes
    """
    store = EventStore(max_events=5000, retention_seconds=86400 * 365)

    # Root process (the "unknown agent")
    store.push_process(ProcessExecEvent(
        timestamp=_BASE,
        pid=1000,
        ppid=1,
        name="python3",
        cmdline="python3 /opt/agent/run.py --autonomous",
        source="polling",
    ))

    # BEH-001: 12 child shells within 36 seconds (scores ~1.0)
    for i in range(12):
        store.push_process(ProcessExecEvent(
            timestamp=_BASE + timedelta(seconds=2 + i * 3),
            pid=1001 + i,
            ppid=1000,
            name="bash",
            cmdline=f"bash -c 'echo task-{i}'",
            source="polling",
        ))

    # BEH-002: 10 LLM API connections within 90 seconds (scores ~1.0)
    for i in range(10):
        store.push_network(NetworkConnectEvent(
            timestamp=_BASE + timedelta(seconds=5 + i * 9),
            pid=1000,
            process_name="python3",
            remote_addr="api.openai.com",
            remote_port=443,
            local_port=50000 + i,
            protocol="tcp",
            sni="api.openai.com",
            source="polling",
        ))

    # BEH-003 (burst write): 15 files across 5 directories within 30 seconds
    for i in range(15):
        store.push_file(FileChangeEvent(
            timestamp=_BASE + timedelta(seconds=10 + i * 2),
            path=f"/tmp/workspace/dir{i % 5}/file{i}.py",
            action="modified",
            pid=1001 + (i % 12),
            process_name="bash",
            source="polling",
        ))

    # BEH-005 (session duration): activity spread over 15 minutes.
    # Add late network and file events so session spans _BASE to _BASE+900s.
    for i in range(5):
        offset = 300 + i * 120  # 5min, 7min, 9min, 11min, 13min
        store.push_network(NetworkConnectEvent(
            timestamp=_BASE + timedelta(seconds=offset),
            pid=1000,
            process_name="python3",
            remote_addr="api.anthropic.com",
            remote_port=443,
            local_port=51000 + i,
            protocol="tcp",
            source="polling",
        ))
        store.push_file(FileChangeEvent(
            timestamp=_BASE + timedelta(seconds=offset + 30),
            path=f"/tmp/workspace/dir{i}/late_output_{i}.py",
            action="modified",
            pid=1001 + (i % 12),
            process_name="bash",
            source="polling",
        ))

    return store


class TestEnforcementEndToEnd(unittest.TestCase):
    """Single test class exercising behavioral detection through enforcement
    through event emission, per Task 9 acceptance criteria."""

    def setUp(self) -> None:
        self.validator = _validator()
        self.kwargs = _base_event_kwargs()

    # -- Step 1+2: Seed EventStore and run BehavioralScanner ----------------

    def test_step1_2_behavioral_detection(self) -> None:
        """BehavioralScanner detects BEH-001 + BEH-002 with confidence >= 0.65."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan(verbose=False)

        self.assertTrue(result.detected, "BehavioralScanner should detect the seeded events")
        self.assertEqual(result.tool_name, "Unknown Agent")
        self.assertIn(result.tool_class, ("C", "D"))

        confidence = compute_confidence(result)
        self.assertGreaterEqual(confidence, 0.65, f"Confidence {confidence} should be >= 0.65")

    # -- Step 3: evaluate_policy returns block ------------------------------

    def test_step3_policy_block_decision(self) -> None:
        """evaluate_policy returns 'block' for the behavioral scan result."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        confidence = compute_confidence(result)
        conf_class = classify_confidence(confidence)

        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=result.tool_class or "C",
            sensitivity="Tier1",
            action_risk=result.action_risk,
            is_containerized=False,
        )

        self.assertEqual(
            decision.decision_state, "block",
            f"Expected block, got {decision.decision_state} "
            f"(rule={decision.rule_id}, reasons={decision.reason_codes})",
        )

    # -- Steps 4+5: PostureManager active + Enforcer dry-run ---------------

    def test_step4_5_enforcement_simulated(self) -> None:
        """Enforcer in dry-run mode produces a simulated enforcement result."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        confidence = compute_confidence(result)
        conf_class = classify_confidence(confidence)

        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=result.tool_class or "C",
            sensitivity="Tier1",
            action_risk=result.action_risk,
            is_containerized=False,
        )

        with tempfile.TemporaryDirectory() as state_dir:
            posture_mgr = PostureManager(
                initial_posture="active",
                initial_threshold=0.60,
                state_dir=Path(state_dir),
            )
            enforcer = Enforcer(posture_manager=posture_mgr, dry_run=True)

            enf_result = enforcer.enforce(
                decision=decision,
                tool_name=result.tool_name or "Unknown Agent",
                tool_class=result.tool_class or "C",
                pids={1000},
            )

        self.assertTrue(enf_result.simulated, "dry-run should produce a simulated result")
        self.assertIn(enf_result.tactic, ("process_kill", "log_and_alert"))

        event = build_event(
            event_type="enforcement.simulated",
            scan=result,
            confidence=confidence,
            policy=decision,
            enforcement=enf_result,
            **self.kwargs,
        )

        self.assertEqual(event["event_type"], "enforcement.simulated")
        self.assertTrue(event["enforcement"]["simulated"])

    # -- Step 6: Active posture with mocked kill ----------------------------

    def test_step6_enforcement_active_kill(self) -> None:
        """Active posture enforcer attempts process kill (mocked)."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        confidence = compute_confidence(result)
        conf_class = classify_confidence(confidence)

        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=result.tool_class or "C",
            sensitivity="Tier1",
            action_risk=result.action_risk,
            is_containerized=False,
        )

        with tempfile.TemporaryDirectory() as state_dir:
            posture_mgr = PostureManager(
                initial_posture="active",
                initial_threshold=0.60,
                state_dir=Path(state_dir),
            )
            enforcer = Enforcer(posture_manager=posture_mgr, dry_run=False)

            mock_proc = mock.Mock()
            mock_proc.pid = 1000
            mock_proc.cmdline.return_value = ["python3", "/opt/agent/run.py", "--autonomous"]
            mock_proc.children.return_value = []
            mock_proc.send_signal = mock.Mock()

            m_psutil = mock.MagicMock()
            m_psutil.Process.return_value = mock_proc
            m_psutil.wait_procs.return_value = ([mock_proc], [])

            with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
                with mock.patch("enforcement.process_kill.os.killpg"), \
                     mock.patch("enforcement.process_kill.os.getpgid"):
                    enf_result = enforcer.enforce(
                        decision=decision,
                        tool_name=result.tool_name or "Unknown Agent",
                        tool_class=result.tool_class or "C",
                        pids={1000},
                        process_patterns=result.process_patterns,
                    )

        self.assertFalse(enf_result.simulated, "Active posture should not simulate")
        self.assertEqual(enf_result.tactic, "process_kill")
        self.assertTrue(enf_result.success, f"Kill should succeed; detail: {enf_result.detail}")

    # -- Step 7: Event schema compliance ------------------------------------

    def test_step7_enforcement_applied_schema_compliance(self) -> None:
        """enforcement.applied event validates against canonical-event-schema.json."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        confidence = compute_confidence(result)
        conf_class = classify_confidence(confidence)

        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=result.tool_class or "C",
            sensitivity="Tier1",
            action_risk=result.action_risk,
            is_containerized=False,
        )

        applied_result = EnforcementResult(
            tactic="process_kill",
            success=True,
            detail="Process terminated: PID 1000",
            tool_name="Unknown Agent",
            simulated=False,
        )

        event = build_event(
            event_type="enforcement.applied",
            scan=result,
            confidence=confidence,
            policy=decision,
            enforcement=applied_result,
            **self.kwargs,
        )

        errors = self.validator.validate(event)
        self.assertEqual(errors, [], f"Schema validation failed: {errors}")
        self.assertIn("enforcement", event)
        self.assertEqual(event["enforcement"]["tactic"], "process_kill")
        self.assertTrue(event["enforcement"]["success"])
        self.assertIn("outcome", event)
        self.assertEqual(event["outcome"]["enforcement_result"], "denied")
        self.assertIn("policy", event)
        self.assertEqual(event["policy"]["decision_state"], "block")

    def test_step7_enforcement_simulated_event_structure(self) -> None:
        """enforcement.simulated event has correct structure and fields."""
        store = _seed_event_store()
        scanner = BehavioralScanner(event_store=store)
        result = scanner.scan()
        confidence = compute_confidence(result)
        conf_class = classify_confidence(confidence)

        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=result.tool_class or "C",
            sensitivity="Tier1",
            action_risk=result.action_risk,
            is_containerized=False,
        )

        simulated_result = EnforcementResult(
            tactic="process_kill",
            success=True,
            detail="[AUDIT] Would kill PIDs {1000} for Unknown Agent",
            tool_name="Unknown Agent",
            simulated=True,
        )

        event = build_event(
            event_type="enforcement.simulated",
            scan=result,
            confidence=confidence,
            policy=decision,
            enforcement=simulated_result,
            **self.kwargs,
        )

        self.assertEqual(event["event_type"], "enforcement.simulated")
        self.assertIn("enforcement", event)
        self.assertTrue(event["enforcement"]["simulated"])
        self.assertEqual(event["enforcement"]["tactic"], "process_kill")
        self.assertIn("outcome", event)
        self.assertIn("policy", event)
        self.assertEqual(event["policy"]["decision_state"], "block")

    # -- Step 8: Webhook dispatcher matching --------------------------------

    def test_step8_webhook_dispatcher_fires(self) -> None:
        """Webhook dispatcher would fire for enforcement event types."""
        # The webhook dispatcher lives in api/, so we test _matches directly
        # to avoid importing the full FastAPI app.
        api_dir = str(_repo_root() / "api")
        if api_dir not in sys.path:
            sys.path.insert(0, api_dir)

        from webhooks.dispatcher import _matches

        enforcement_types = [
            "enforcement.simulated",
            "enforcement.applied",
            "enforcement.allow_listed",
            "enforcement.rate_limited",
        ]

        # Webhook subscribed to all enforcement events
        subscribed = json.dumps(enforcement_types)
        for et in enforcement_types:
            self.assertTrue(
                _matches(subscribed, et, "block"),
                f"Webhook should match event_type={et}",
            )

        # Webhook subscribed to block decision_state
        decision_sub = json.dumps(["block"])
        self.assertTrue(
            _matches(decision_sub, "enforcement.applied", "block"),
            "Webhook should match decision_state='block'",
        )

        # Webhook with empty subscription matches everything
        self.assertTrue(
            _matches("[]", "enforcement.simulated", None),
            "Empty subscription should match any event",
        )

        # Webhook NOT subscribed should not match
        irrelevant = json.dumps(["detection.observed"])
        self.assertFalse(
            _matches(irrelevant, "enforcement.applied", None),
            "Unsubscribed webhook should not match enforcement events",
        )


class TestFullPipelineIntegration(unittest.TestCase):
    """Runs the complete pipeline in sequence: seed -> scan -> policy ->
    enforce (simulated) -> enforce (active) -> validate schema -> check webhook.

    This is the single-method variant that mirrors the Task 9 scenario
    steps 1-8 in order, verifying the chain holds end-to-end."""

    def test_full_chain(self) -> None:
        validator = _validator()
        kwargs = _base_event_kwargs()

        # Step 1: Seed EventStore
        store = _seed_event_store()

        # Step 2: Run BehavioralScanner
        scanner = BehavioralScanner(event_store=store)
        scan = scanner.scan()
        self.assertTrue(scan.detected)
        confidence = compute_confidence(scan)
        self.assertGreaterEqual(confidence, 0.65)

        # Step 3: evaluate_policy -> block
        conf_class = classify_confidence(confidence)
        decision = evaluate_policy(
            confidence=confidence,
            confidence_class=conf_class,
            tool_class=scan.tool_class or "C",
            sensitivity="Tier1",
            action_risk=scan.action_risk,
            is_containerized=False,
        )
        self.assertEqual(decision.decision_state, "block")

        # Step 4+5: PostureManager active, Enforcer dry-run -> simulated
        posture_mgr = PostureManager(
            initial_posture="active",
            initial_threshold=0.60,
            state_dir=None,
        )
        enforcer_dry = Enforcer(posture_manager=posture_mgr, dry_run=True)
        enf_sim = enforcer_dry.enforce(
            decision=decision,
            tool_name=scan.tool_name or "Unknown Agent",
            tool_class=scan.tool_class or "C",
            pids={1000},
        )
        self.assertTrue(enf_sim.simulated)

        sim_event = build_event(
            event_type="enforcement.simulated",
            scan=scan,
            confidence=confidence,
            policy=decision,
            enforcement=enf_sim,
            **kwargs,
        )
        self.assertEqual(sim_event["event_type"], "enforcement.simulated")
        self.assertTrue(sim_event["enforcement"]["simulated"])

        # Step 6: Active posture, real enforce with mocked kill
        enforcer_real = Enforcer(posture_manager=posture_mgr, dry_run=False)

        mock_proc = mock.Mock()
        mock_proc.pid = 1000
        mock_proc.cmdline.return_value = ["python3", "/opt/agent/run.py"]
        mock_proc.children.return_value = []
        mock_proc.send_signal = mock.Mock()

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = mock_proc
        m_psutil.wait_procs.return_value = ([mock_proc], [])

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg"), \
                 mock.patch("enforcement.process_kill.os.getpgid"):
                enf_real = enforcer_real.enforce(
                    decision=decision,
                    tool_name=scan.tool_name or "Unknown Agent",
                    tool_class=scan.tool_class or "C",
                    pids={1000},
                    process_patterns=scan.process_patterns,
                )
        self.assertFalse(enf_real.simulated)
        self.assertTrue(enf_real.success)

        # Step 7: Schema compliance for the applied event
        applied_event = build_event(
            event_type="enforcement.applied",
            scan=scan,
            confidence=confidence,
            policy=decision,
            enforcement=enf_real,
            **kwargs,
        )
        errors = validator.validate(applied_event)
        self.assertEqual(errors, [], f"Schema errors: {errors}")
        self.assertEqual(applied_event["outcome"]["enforcement_result"], "denied")

        # Step 8: Webhook dispatcher matching
        api_dir = str(_repo_root() / "api")
        if api_dir not in sys.path:
            sys.path.insert(0, api_dir)
        from webhooks.dispatcher import _matches

        self.assertTrue(_matches(
            json.dumps(["enforcement.applied", "enforcement.simulated"]),
            "enforcement.applied",
            "block",
        ))


if __name__ == "__main__":
    unittest.main()
