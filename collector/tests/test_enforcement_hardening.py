"""Tests for Phase 3 Enforcement Hardening: process kill, rate limiter, cleanup, resurrection."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest

_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from enforcement.process_kill import kill_process_tree, KillResult
from enforcement.rate_limiter import EnforcementRateLimiter
from enforcement.cleanup import cleanup_orphaned_rules
from enforcement.enforcer import Enforcer, EnforcementResult
from engine.policy import PolicyDecision


# -- kill_process_tree tests -------------------------------------------------


class TestKillProcessTree:
    def test_successful_tree_kill_children_first(self) -> None:
        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.return_value = ["/usr/bin/cursor", "run"]
        child1 = mock.Mock()
        child1.pid = 101
        child2 = mock.Mock()
        child2.pid = 102
        parent.children.return_value = [child1, child2]
        child1.children.return_value = []
        child2.children.return_value = []

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent
        m_psutil.wait_procs.return_value = ([parent, child1, child2], [])

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg"), mock.patch(
                "enforcement.process_kill.os.getpgid"
            ):
                result = kill_process_tree(100, expected_pattern="cursor")

        assert result.success is True
        assert result.killed_pids == [101, 102, 100]
        assert len(result.killed_pids) == 3
        for p in [child1, child2, parent]:
            p.send_signal.assert_called_once_with(mock.ANY)

    def test_pid_verification_rejects_mismatched_cmdline(self) -> None:
        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.return_value = ["/usr/bin/other-app", "run"]

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg"), mock.patch(
                "enforcement.process_kill.os.getpgid"
            ):
                result = kill_process_tree(100, expected_pattern="cursor")

        assert result.success is False
        assert "cmdline mismatch" in result.detail.lower()
        parent.send_signal.assert_not_called()

    def test_already_gone_returns_success(self) -> None:
        import psutil

        m_psutil = mock.MagicMock()
        m_psutil.Process.side_effect = psutil.NoSuchProcess(100)
        m_psutil.NoSuchProcess = psutil.NoSuchProcess
        m_psutil.AccessDenied = psutil.AccessDenied

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            result = kill_process_tree(100)

        assert result.success is True
        assert "already gone" in result.detail.lower()

    def test_killpg_attempted_before_individual_kills(self) -> None:
        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.return_value = ["cursor"]
        parent.children.return_value = []

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent
        m_psutil.wait_procs.return_value = ([parent], [])

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg") as m_killpg:
                with mock.patch("enforcement.process_kill.os.getpgid", return_value=100):
                    result = kill_process_tree(100)

        m_killpg.assert_called_once()
        assert result.success is True

    def test_access_denied_on_cmdline_returns_failure(self) -> None:
        import psutil

        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.side_effect = psutil.AccessDenied(100)

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent
        m_psutil.NoSuchProcess = psutil.NoSuchProcess
        m_psutil.AccessDenied = psutil.AccessDenied

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            result = kill_process_tree(100, expected_pattern="cursor")

        assert result.success is False
        assert "cmdline" in result.detail.lower()

    def test_access_denied_on_signal_continues(self) -> None:
        import psutil

        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.return_value = ["cursor"]
        parent.children.return_value = []
        parent.send_signal.side_effect = psutil.AccessDenied(100)
        parent.kill.side_effect = psutil.AccessDenied(100)

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent
        m_psutil.wait_procs.return_value = ([], [parent])
        m_psutil.NoSuchProcess = psutil.NoSuchProcess
        m_psutil.AccessDenied = psutil.AccessDenied

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg"), mock.patch(
                "enforcement.process_kill.os.getpgid"
            ):
                result = kill_process_tree(100)

        assert result.success is True
        assert result.killed_pids == [100]

    def test_single_process_no_children(self) -> None:
        parent = mock.Mock()
        parent.pid = 100
        parent.cmdline.return_value = ["cursor"]
        parent.children.return_value = []

        m_psutil = mock.MagicMock()
        m_psutil.Process.return_value = parent
        m_psutil.wait_procs.return_value = ([parent], [])

        with mock.patch.dict("sys.modules", {"psutil": m_psutil}):
            with mock.patch("enforcement.process_kill.os.killpg"), mock.patch(
                "enforcement.process_kill.os.getpgid"
            ):
                result = kill_process_tree(100)

        assert result.success is True
        assert result.killed_pids == [100]
        assert "killed 1" in result.detail

    def test_skipped_pid_le_1(self) -> None:
        result = kill_process_tree(1)
        assert result.success is False
        assert "skipped" in result.detail.lower()

        result = kill_process_tree(0)
        assert result.success is False


# -- EnforcementRateLimiter tests ---------------------------------------------


class TestEnforcementRateLimiter:
    def test_allows_actions_under_limit(self) -> None:
        limiter = EnforcementRateLimiter(max_per_minute=3)
        assert limiter.allow() is True
        limiter.record()
        assert limiter.allow() is True
        limiter.record()
        assert limiter.allow() is True

    def test_blocks_after_limit_exceeded(self) -> None:
        limiter = EnforcementRateLimiter(max_per_minute=2)
        assert limiter.allow() is True
        limiter.record()
        assert limiter.allow() is True
        limiter.record()
        assert limiter.allow() is False
        assert limiter.allow() is False

    def test_window_slides_old_entries_expire(self) -> None:
        with mock.patch("enforcement.rate_limiter.time.monotonic", return_value=0.0):
            limiter = EnforcementRateLimiter(max_per_minute=2)
            limiter.record()
            limiter.record()
            assert limiter.allow() is False

        with mock.patch("enforcement.rate_limiter.time.monotonic", return_value=61.0):
            assert limiter.allow() is True

    def test_custom_limit_parameters(self) -> None:
        limiter = EnforcementRateLimiter(max_per_minute=10)
        for _ in range(9):
            assert limiter.allow() is True
            limiter.record()
        assert limiter.allow() is True
        limiter.record()
        assert limiter.allow() is False

        limiter2 = EnforcementRateLimiter(max_per_minute=1)
        assert limiter2.allow() is True
        limiter2.record()
        assert limiter2.allow() is False


# -- cleanup_orphaned_rules tests ---------------------------------------------


class TestCleanupOrphanedRules:
    def test_macos_pf_anchor_cleanup(self) -> None:
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m_run:
                m_run.side_effect = [
                    mock.Mock(returncode=0, stdout="rule1\nrule2\n"),
                    mock.Mock(returncode=0),
                ]
                count = cleanup_orphaned_rules()
        assert count == 2
        assert m_run.call_count >= 2

    def test_linux_iptables_cleanup(self) -> None:
        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("subprocess.run") as m_run:
                m_run.side_effect = [
                    mock.Mock(returncode=0, stdout="-A OUTPUT -j DROP agentic-gov-block\n"),
                    mock.Mock(returncode=0),
                ]
                count = cleanup_orphaned_rules()
        assert count == 1

    def test_windows_netsh_cleanup(self) -> None:
        with mock.patch("platform.system", return_value="Windows"):
            with mock.patch("subprocess.run") as m_run:
                m_run.side_effect = [
                    mock.Mock(
                        returncode=0,
                        stdout="Rule Name: agentic-gov-block-123\nRule Name: other\n",
                    ),
                    mock.Mock(returncode=0),
                ]
                count = cleanup_orphaned_rules()
        assert count == 1

    def test_no_errors_when_no_rules_exist(self) -> None:
        with mock.patch("platform.system", return_value="Darwin"):
            with mock.patch("subprocess.run") as m_run:
                m_run.return_value = mock.Mock(returncode=1, stdout="")
                count = cleanup_orphaned_rules()
        assert count == 0

        with mock.patch("platform.system", return_value="Linux"):
            with mock.patch("subprocess.run") as m_run:
                m_run.return_value = mock.Mock(returncode=0, stdout="-A OUTPUT -j ACCEPT\n")
                count = cleanup_orphaned_rules()
        assert count == 0

        with mock.patch("platform.system", return_value="Windows"):
            with mock.patch("subprocess.run") as m_run:
                m_run.return_value = mock.Mock(returncode=0, stdout="Rule Name: other-rule\n")
                count = cleanup_orphaned_rules()
        assert count == 0


# -- Resurrection detection tests ---------------------------------------------


def _make_decision(state: str = "block", confidence: float = 0.85) -> PolicyDecision:
    return PolicyDecision(
        decision_state=state,
        rule_id="ENFORCE-004",
        rule_version="0.4.0",
        reason_codes=["test"],
        decision_confidence=confidence,
    )


class TestResurrectionDetection:
    def test_first_kill_not_escalated(self, tmp_path: Path) -> None:
        from enforcement.posture import PostureManager

        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr, max_enforcements_per_minute=10)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            result = enforcer.enforce(
                decision=_make_decision("block"),
                tool_name="Cursor",
                tool_class="C",
                pids={999},
            )

        assert result.escalated is False
        assert "Escalated" not in result.detail

    def test_third_kill_within_5_minutes_escalated(self, tmp_path: Path) -> None:
        from enforcement.posture import PostureManager

        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr, max_enforcements_per_minute=10)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            for _ in range(3):
                result = enforcer.enforce(
                    decision=_make_decision("block"),
                    tool_name="Cursor",
                    tool_class="C",
                    pids={999},
                )

        assert result.escalated is True
        assert "Escalated" in result.detail

    def test_kills_outside_window_not_escalated(self, tmp_path: Path) -> None:
        from enforcement.posture import PostureManager

        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr, max_enforcements_per_minute=10)

        time_values = [0.0] * 4 + [310.0] * 4 + [620.0] * 4

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("enforcement.rate_limiter.time.monotonic", side_effect=time_values):
                    r1 = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="Cursor",
                        tool_class="C",
                        pids={999},
                    )
                    r2 = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="Cursor",
                        tool_class="C",
                        pids={999},
                    )
                    r3 = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="Cursor",
                        tool_class="C",
                        pids={999},
                    )

        assert r1.escalated is False
        assert r2.escalated is False
        assert r3.escalated is False
