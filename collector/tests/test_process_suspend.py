"""Tests for SIGSTOP-based process suspension during approval holds (P4b).

Covers:
  - suspend_processes sends SIGSTOP to each PID
  - suspend_processes handles missing PIDs (ProcessLookupError)
  - suspend_processes handles permission errors (PermissionError)
  - resume_processes sends SIGCONT to each PID
  - resume on already-running process is safe (no-op)
  - Windows platform returns all False
  - ApprovalHoldManager suspends when enabled
  - ApprovalHoldManager resumes on approve
  - ApprovalHoldManager does NOT resume on deny
  - Safety valve resumes after max_suspend_seconds
  - finally block resumes on exception
  - HoldResult.hold_effective=True when SIGSTOP succeeded
  - SIGSTOP not counted as kill in resurrection detector
"""

from __future__ import annotations

import signal
import time
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, call, patch

import pytest

from enforcement.process_suspend import resume_processes, suspend_processes


# ---------------------------------------------------------------------------
# Unit tests: suspend_processes / resume_processes
# ---------------------------------------------------------------------------


class TestSuspendProcesses:
    """Tests for the suspend_processes() function."""

    def test_suspend_processes_sends_sigstop(self) -> None:
        """SIGSTOP is sent to each PID via os.kill."""
        with patch("enforcement.process_suspend.os.kill") as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Darwin"):
            result = suspend_processes({100, 200})

        assert result == {100: True, 200: True}
        m_kill.assert_any_call(100, signal.SIGSTOP)
        m_kill.assert_any_call(200, signal.SIGSTOP)
        assert m_kill.call_count == 2

    def test_suspend_handles_missing_pid(self) -> None:
        """ProcessLookupError is handled gracefully; PID returns False."""
        with patch("enforcement.process_suspend.os.kill", side_effect=ProcessLookupError) as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = suspend_processes({999})

        assert result == {999: False}
        m_kill.assert_called_once_with(999, signal.SIGSTOP)

    def test_suspend_handles_permission_error(self) -> None:
        """PermissionError is handled gracefully; PID returns False."""
        with patch("enforcement.process_suspend.os.kill", side_effect=PermissionError) as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = suspend_processes({42})

        assert result == {42: False}

    def test_suspend_handles_oserror(self) -> None:
        """Generic OSError is handled gracefully."""
        with patch("enforcement.process_suspend.os.kill", side_effect=OSError("test")) as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = suspend_processes({55})

        assert result == {55: False}

    def test_suspend_skips_system_pids(self) -> None:
        """PIDs <= 1 are refused for safety."""
        with patch("enforcement.process_suspend.os.kill") as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = suspend_processes({0, 1})

        assert result == {0: False, 1: False}
        m_kill.assert_not_called()

    def test_suspend_mixed_results(self) -> None:
        """Mix of successful and failing PIDs returns correct results."""
        def _side_effect(pid, sig):
            if pid == 100:
                return None
            raise ProcessLookupError

        with patch("enforcement.process_suspend.os.kill", side_effect=_side_effect), \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = suspend_processes({100, 200})

        assert result[100] is True
        assert result[200] is False


class TestResumeProcesses:
    """Tests for the resume_processes() function."""

    def test_resume_processes_sends_sigcont(self) -> None:
        """SIGCONT is sent to each PID via os.kill."""
        with patch("enforcement.process_suspend.os.kill") as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Darwin"):
            result = resume_processes({100, 200})

        assert result == {100: True, 200: True}
        m_kill.assert_any_call(100, signal.SIGCONT)
        m_kill.assert_any_call(200, signal.SIGCONT)

    def test_resume_safe_on_running_process(self) -> None:
        """SIGCONT on a non-stopped (running) process succeeds — it is a no-op."""
        with patch("enforcement.process_suspend.os.kill") as m_kill, \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            # os.kill with SIGCONT on a running process does not raise
            m_kill.return_value = None
            result = resume_processes({300})

        assert result == {300: True}
        m_kill.assert_called_once_with(300, signal.SIGCONT)

    def test_resume_handles_errors(self) -> None:
        """Errors during SIGCONT are handled gracefully."""
        with patch("enforcement.process_suspend.os.kill", side_effect=ProcessLookupError), \
             patch("enforcement.process_suspend.platform.system", return_value="Linux"):
            result = resume_processes({404})

        assert result == {404: False}


class TestWindowsPlatform:
    """Tests for Windows platform behavior."""

    def test_windows_suspend_returns_false(self) -> None:
        """On Windows (mocked), suspend_processes returns all False."""
        with patch("enforcement.process_suspend.platform.system", return_value="Windows"):
            result = suspend_processes({100, 200, 300})

        assert result == {100: False, 200: False, 300: False}

    def test_windows_resume_returns_false(self) -> None:
        """On Windows (mocked), resume_processes returns all False."""
        with patch("enforcement.process_suspend.platform.system", return_value="Windows"):
            result = resume_processes({100, 200})

        assert result == {100: False, 200: False}


# ---------------------------------------------------------------------------
# Integration tests: ApprovalHoldManager with suspension
# ---------------------------------------------------------------------------


class TestApprovalHoldSuspension:
    """Tests for SIGSTOP integration in ApprovalHoldManager.wait_for_decision."""

    def _make_manager(self, **hold_config_kwargs):
        from enforcement.approval_hold import ApprovalHoldManager, HoldConfig
        # Allow callers to override defaults via kwargs.
        defaults = {"poll_interval_seconds": 0, "timeout_seconds": 10}
        defaults.update(hold_config_kwargs)
        config = HoldConfig(**defaults)
        return ApprovalHoldManager(
            api_url="http://localhost:8000/api",
            api_key="test-key",
            config=config,
        )

    def _common_kwargs(self):
        return dict(
            event_id="evt-1",
            tool_name="cursor",
            tool_class="C",
            confidence_band="high",
            confidence_score=0.9,
            policy_rule_id="RULE-1",
        )

    def test_approval_hold_suspends_when_enabled(self) -> None:
        """When suspend_on_hold=True and pids given, suspend_processes is called."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
             patch.object(manager, "_poll_decision", return_value="approved"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True, 200: True}) as m_suspend, \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True, 200: True}) as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100, 200},
                suspend_on_hold=True,
                max_suspend_seconds=60,
            )

        m_suspend.assert_called_once_with({100, 200})
        assert result.hold_effective is True

    def test_approval_hold_no_suspend_when_disabled(self) -> None:
        """When suspend_on_hold=False, suspend_processes is NOT called."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
             patch.object(manager, "_poll_decision", return_value="approved"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes") as m_suspend, \
             patch("enforcement.process_suspend.resume_processes") as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=False,
            )

        m_suspend.assert_not_called()
        m_resume.assert_not_called()
        assert result.hold_effective is False

    def test_approval_hold_resumes_on_approve(self) -> None:
        """SIGCONT is sent when the decision is 'approved'."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
             patch.object(manager, "_poll_decision", return_value="approved"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}) as m_suspend, \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}) as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
            )

        assert result.decision == "approved"
        m_resume.assert_called_once_with({100})

    def test_approval_hold_no_resume_on_deny(self) -> None:
        """No SIGCONT when denied -- the enforcer will kill the process."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
             patch.object(manager, "_poll_decision", return_value="denied"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}) as m_suspend, \
             patch("enforcement.process_suspend.resume_processes") as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
            )

        assert result.decision == "denied"
        # resume_processes should NOT be called for a denied decision
        m_resume.assert_not_called()

    def test_safety_valve_resumes_after_max_seconds(self) -> None:
        """Processes are resumed when max_suspend_seconds is exceeded."""
        manager = self._make_manager(timeout_seconds=300)

        # Track monotonic time to simulate the safety valve triggering.
        time_cursor = [0.0]

        def _fake_monotonic():
            return time_cursor[0]

        poll_count = [0]
        def _fake_poll(approval_id):
            poll_count[0] += 1
            if poll_count[0] == 1:
                # First poll: still pending, but advance time past the suspend deadline
                time_cursor[0] = 70.0  # past the 60s safety valve
                return "pending"
            if poll_count[0] == 2:
                return "pending"
            return "approved"

        with patch.object(manager, "_create_approval_request", return_value="ar-sv"), \
             patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.approval_hold.time.monotonic", side_effect=_fake_monotonic), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}) as m_suspend, \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}) as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
                max_suspend_seconds=60,
            )

        assert result.decision == "approved"
        # resume should have been called by the safety valve during the loop,
        # then possibly again at the end for the approved decision (but the set
        # will be empty by then, so the second call is a no-op).
        assert m_resume.call_count >= 1
        # The first resume call should be the safety valve with the suspended PIDs.
        m_resume.assert_any_call({100})

    def test_finally_resumes_on_exception(self) -> None:
        """If an unexpected exception occurs, the finally block resumes PIDs."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-ex"), \
             patch.object(manager, "_poll_decision", side_effect=RuntimeError("boom")), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}), \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}) as m_resume:
            # The RuntimeError should be caught by the general except in poll,
            # but RequestException is checked specifically. Let's use a scenario
            # where the exception propagates through the finally.
            pass

        # For a proper finally-block test, we need an exception that escapes
        # the while loop entirely. We can do this by making time.monotonic raise.
        manager2 = self._make_manager()

        with patch.object(manager2, "_create_approval_request", return_value="ar-ex2"), \
             patch("enforcement.approval_hold.time.monotonic") as m_mono, \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}), \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}) as m_resume2:
            # First call sets the deadline, second call is for suspend_deadline,
            # third call in the safety valve check raises an exception.
            call_count = [0]
            def _monotonic_bomb():
                call_count[0] += 1
                if call_count[0] <= 2:
                    return 0.0
                raise RuntimeError("unexpected failure")

            m_mono.side_effect = _monotonic_bomb

            with pytest.raises(RuntimeError, match="unexpected failure"):
                manager2.wait_for_decision(
                    **self._common_kwargs(),
                    pids={100},
                    suspend_on_hold=True,
                )

        # The finally block should have resumed the suspended PIDs.
        m_resume2.assert_called_with({100})

    def test_hold_effective_true_when_suspended(self) -> None:
        """HoldResult.hold_effective is True when at least one PID was SIGSTOP'd."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-he"), \
             patch.object(manager, "_poll_decision", return_value="approved"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True, 200: False}), \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}):
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100, 200},
                suspend_on_hold=True,
            )

        assert result.hold_effective is True

    def test_hold_effective_false_when_no_pid_suspended(self) -> None:
        """HoldResult.hold_effective is False when no PIDs could be suspended."""
        manager = self._make_manager()

        with patch.object(manager, "_create_approval_request", return_value="ar-nhe"), \
             patch.object(manager, "_poll_decision", return_value="approved"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: False}), \
             patch("enforcement.process_suspend.resume_processes"):
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
            )

        assert result.hold_effective is False

    def test_timeout_deny_no_resume(self) -> None:
        """On timeout with timeout_behavior=deny, processes are NOT resumed."""
        manager = self._make_manager(timeout_seconds=0, timeout_behavior="deny")

        with patch.object(manager, "_create_approval_request", return_value="ar-td"), \
             patch.object(manager, "_poll_decision", return_value="pending"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}), \
             patch("enforcement.process_suspend.resume_processes") as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
            )

        assert result.timed_out is True
        assert result.decision == "denied"
        # Should NOT resume on deny timeout
        m_resume.assert_not_called()

    def test_timeout_approve_resumes(self) -> None:
        """On timeout with timeout_behavior=approve, processes ARE resumed."""
        manager = self._make_manager(timeout_seconds=0, timeout_behavior="approve")

        with patch.object(manager, "_create_approval_request", return_value="ar-ta"), \
             patch.object(manager, "_poll_decision", return_value="pending"), \
             patch("enforcement.approval_hold.time.sleep"), \
             patch("enforcement.process_suspend.suspend_processes", return_value={100: True}), \
             patch("enforcement.process_suspend.resume_processes", return_value={100: True}) as m_resume:
            result = manager.wait_for_decision(
                **self._common_kwargs(),
                pids={100},
                suspend_on_hold=True,
            )

        assert result.timed_out is True
        assert result.decision == "approved"
        m_resume.assert_called_once_with({100})


# ---------------------------------------------------------------------------
# Guard: SIGSTOP must NOT be counted as kill in resurrection detector
# ---------------------------------------------------------------------------


class TestSigstopNotCountedAsKill:
    """Verify that SIGSTOP (approval hold) does not pollute kill history."""

    def test_sigstop_not_counted_as_kill(self, tmp_path: Path) -> None:
        """The enforcer's approval_required path must not increment kill_history.

        This is critical: if SIGSTOP'd processes were counted as "killed",
        the resurrection detector would falsely escalate after 3 approval
        holds, potentially killing parent shells and disabling services.
        """
        from enforcement.enforcer import Enforcer
        from enforcement.posture import PostureManager
        from engine.policy import PolicyDecision

        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(
            posture_manager=mgr,
            max_enforcements_per_minute=20,
            suspend_on_hold=True,
            max_suspend_seconds=60,
        )

        decision = PolicyDecision(
            decision_state="approval_required",
            rule_id="RULE-HOLD",
            rule_version="1.0",
            reason_codes=["test_hold"],
            decision_confidence=0.9,
        )

        # Fire the approval_required path 5 times with PIDs
        for _ in range(5):
            result = enforcer.enforce(
                decision=decision,
                tool_name="SuspectedAgent",
                tool_class="C",
                pids={100, 200},
            )
            assert result.tactic == "hold_pending_approval"

        # The kill history should be empty -- approval_required never records kills
        assert "SuspectedAgent" not in enforcer._kill_history
        # No escalation flag on any result
        assert result.escalated is False


# ---------------------------------------------------------------------------
# Config loader integration tests
# ---------------------------------------------------------------------------


class TestConfigLoaderSuspendKeys:
    """Verify config_loader properly loads suspend_on_hold and max_suspend_seconds."""

    def test_enforcement_defaults_include_suspend_keys(self, tmp_path: Path) -> None:
        """Default enforcement config includes suspend_on_hold and max_suspend_seconds."""
        import json
        from config_loader import load_collector_config

        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps({}))
        cfg = load_collector_config(config_file)

        assert cfg["enforcement"]["suspend_on_hold"] is False
        assert cfg["enforcement"]["max_suspend_seconds"] == 60

    def test_enforcement_config_from_file(self, tmp_path: Path) -> None:
        """suspend_on_hold and max_suspend_seconds can be set from config file."""
        import json
        from config_loader import load_collector_config

        config_data = {
            "enforcement": {
                "suspend_on_hold": True,
                "max_suspend_seconds": 120,
            }
        }
        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps(config_data))
        cfg = load_collector_config(config_file)

        assert cfg["enforcement"]["suspend_on_hold"] is True
        assert cfg["enforcement"]["max_suspend_seconds"] == 120

    def test_enforcement_env_override_suspend_keys(self, tmp_path: Path) -> None:
        """Environment variables override suspend_on_hold and max_suspend_seconds."""
        import json
        from config_loader import load_collector_config

        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps({}))

        with mock.patch.dict("os.environ", {
            "AGENTIC_GOV_ENFORCEMENT_SUSPEND_ON_HOLD": "true",
            "AGENTIC_GOV_ENFORCEMENT_MAX_SUSPEND_SECONDS": "30",
        }):
            cfg = load_collector_config(config_file)

        assert cfg["enforcement"]["suspend_on_hold"] is True
        assert cfg["enforcement"]["max_suspend_seconds"] == 30

    def test_enforcement_env_invalid_max_suspend_seconds(self, tmp_path: Path) -> None:
        """Invalid integer for max_suspend_seconds is ignored."""
        import json
        from config_loader import load_collector_config

        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps({}))

        with mock.patch.dict("os.environ", {
            "AGENTIC_GOV_ENFORCEMENT_MAX_SUSPEND_SECONDS": "not-a-number",
        }):
            cfg = load_collector_config(config_file)

        # Should fall back to default
        assert cfg["enforcement"]["max_suspend_seconds"] == 60
