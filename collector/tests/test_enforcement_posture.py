"""Tests for enforcement posture manager and posture-aware enforcer."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from enforcement.posture import PostureManager, DEFAULT_ALLOW_LIST_MAX_AGE
from enforcement.enforcer import Enforcer, EnforcementResult
from engine.policy import PolicyDecision


# -- PostureManager tests ---------------------------------------------------

class TestPostureManager:
    def test_defaults(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        assert mgr.posture == "passive"
        assert mgr.auto_enforce_threshold == 0.75
        assert mgr.allow_list == []
        assert mgr.source == "config"

    def test_update_posture(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        mgr.update("active", auto_enforce_threshold=0.80, source="server_push")
        assert mgr.posture == "active"
        assert mgr.auto_enforce_threshold == 0.80
        assert mgr.source == "server_push"

    def test_update_allow_list(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        mgr.update("audit", allow_list=["cursor", "copilot"])
        assert mgr.allow_list == ["cursor", "copilot"]

    def test_invalid_posture_rejected(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        mgr.update("invalid_posture")
        assert mgr.posture == "passive"

    def test_persistence(self, tmp_path: Path) -> None:
        mgr1 = PostureManager(state_dir=tmp_path)
        mgr1.update("active", auto_enforce_threshold=0.90, allow_list=["tool1"])

        mgr2 = PostureManager(state_dir=tmp_path)
        assert mgr2.posture == "active"
        assert mgr2.auto_enforce_threshold == 0.90
        assert mgr2.allow_list == ["tool1"]

    def test_is_allow_listed(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        mgr.update("active", allow_list=["cursor", "copilot"])
        assert mgr.is_allow_listed("Cursor") is True
        assert mgr.is_allow_listed("GitHub Copilot") is True
        assert mgr.is_allow_listed("Ollama") is False

    def test_initial_values_from_args(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="audit",
            initial_threshold=0.60,
            state_dir=tmp_path,
        )
        assert mgr.posture == "audit"
        assert mgr.auto_enforce_threshold == 0.60

    def test_corrupted_state_file(self, tmp_path: Path) -> None:
        state_file = tmp_path / "posture.json"
        state_file.write_text("not valid json")
        mgr = PostureManager(state_dir=tmp_path)
        assert mgr.posture == "passive"


# -- Enforcer posture tests -------------------------------------------------

def _make_decision(state: str = "block", confidence: float = 0.85) -> PolicyDecision:
    return PolicyDecision(
        decision_state=state,
        rule_id="ENFORCE-004",
        rule_version="0.4.0",
        reason_codes=["test"],
        decision_confidence=confidence,
    )


class TestEnforcerPosture:
    def test_passive_never_enforces(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="passive", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="TestTool",
            tool_class="C",
            pids={999},
        )
        assert result.tactic == "log_and_alert"
        assert "passive" in result.detail.lower()

    def test_audit_simulates(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="audit", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="TestTool",
            tool_class="C",
            pids={999},
        )
        assert result.tactic == "process_kill"
        assert result.simulated is True
        assert "[AUDIT]" in result.detail

    def test_audit_simulates_network_block(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="audit", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="TestTool",
            tool_class="C",
            pids={999},
            network_elevated=True,
        )
        assert result.tactic == "network_null_route"
        assert result.simulated is True

    def test_active_below_threshold_simulates(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="active",
            initial_threshold=0.90,
            state_dir=tmp_path,
        )
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("block", confidence=0.85),
            tool_name="TestTool",
            tool_class="C",
            pids={999},
        )
        assert result.simulated is True
        assert "below" in result.detail.lower()

    def test_allow_list_skips_enforcement(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        mgr.update("active", allow_list=["TestTool"])
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="TestTool",
            tool_class="C",
            pids={999},
        )
        assert result.allow_listed is True
        assert result.tactic == "log_and_alert"

    def test_detect_warn_always_log(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        for state in ("detect", "warn"):
            result = enforcer.enforce(
                decision=_make_decision(state),
                tool_name="TestTool",
                tool_class="A",
            )
            assert result.tactic == "log_and_alert"
            assert result.simulated is False

    def test_approval_required_in_audit(self, tmp_path: Path) -> None:
        mgr = PostureManager(initial_posture="audit", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        result = enforcer.enforce(
            decision=_make_decision("approval_required"),
            tool_name="TestTool",
            tool_class="C",
        )
        assert result.tactic == "hold_pending_approval"
        assert result.simulated is True


# -- Allow-list staleness tests (Task 11a) ----------------------------------

class TestAllowListStaleness:
    """Verify that stale allow-list data causes active enforcement to
    downgrade to audit mode."""

    def test_fresh_after_update(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path)
        mgr.update("active", allow_list=["cursor"])
        assert mgr.is_allow_list_fresh() is True
        assert mgr.allow_list_age_seconds < 5.0

    def test_stale_after_time_passes(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path, allow_list_max_age=1.0)
        mgr.update("active", allow_list=["cursor"])
        # Simulate time passing by backdating the sync timestamp
        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 2.0
        assert mgr.is_allow_list_fresh() is False
        assert mgr.allow_list_age_seconds >= 2.0

    def test_custom_max_age_override(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path, allow_list_max_age=10.0)
        mgr.update("active", allow_list=["cursor"])
        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 5.0
        # Under default max_age (10s), still fresh
        assert mgr.is_allow_list_fresh() is True
        # But stale with a tighter per-call threshold
        assert mgr.is_allow_list_fresh(max_age=3.0) is False

    def test_staleness_persists_across_restart(self, tmp_path: Path) -> None:
        mgr1 = PostureManager(state_dir=tmp_path)
        mgr1.update("active", allow_list=["cursor"])
        # Backdate by 120 seconds
        with mgr1._lock:
            mgr1._allow_list_synced_at = time.monotonic() - 120.0
            mgr1._save()

        mgr2 = PostureManager(state_dir=tmp_path, allow_list_max_age=60.0)
        assert mgr2.is_allow_list_fresh() is False
        assert mgr2.allow_list_age_seconds >= 100.0

    def test_update_without_allow_list_does_not_refresh(self, tmp_path: Path) -> None:
        mgr = PostureManager(state_dir=tmp_path, allow_list_max_age=1.0)
        mgr.update("active", allow_list=["cursor"])
        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 5.0
        assert mgr.is_allow_list_fresh() is False
        # Posture-only update (no allow_list) should not refresh the sync time
        mgr.update("active", auto_enforce_threshold=0.80)
        assert mgr.is_allow_list_fresh() is False

    def test_fresh_on_initial_boot(self, tmp_path: Path) -> None:
        """On first boot with no persisted state, allow-list should be
        treated as fresh to avoid blocking enforcement before the first
        heartbeat arrives."""
        mgr = PostureManager(state_dir=tmp_path, allow_list_max_age=600.0)
        assert mgr.is_allow_list_fresh() is True


class TestEnforcerStalenessGate:
    """Verify the enforcer downgrades to audit when allow-list is stale."""

    def test_active_enforcement_blocked_when_stale(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="active",
            state_dir=tmp_path,
            allow_list_max_age=1.0,
        )
        mgr.update("active", allow_list=["something"])
        enforcer = Enforcer(posture_manager=mgr)

        # Backdate the sync so allow-list is stale
        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 10.0

        result = enforcer.enforce(
            decision=_make_decision("block", confidence=0.95),
            tool_name="NewTool",
            tool_class="C",
            pids={999},
        )
        assert result.simulated is True
        assert "STALE ALLOW-LIST" in result.detail

    def test_active_enforcement_proceeds_when_fresh(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="active",
            state_dir=tmp_path,
            allow_list_max_age=600.0,
        )
        mgr.update("active", allow_list=["something"])
        enforcer = Enforcer(posture_manager=mgr)

        from enforcement.process_kill import KillResult
        with patch("enforcement.process_kill.kill_process_tree") as mock_kill:
            mock_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999])
            result = enforcer.enforce(
                decision=_make_decision("block", confidence=0.95),
                tool_name="NewTool",
                tool_class="C",
                pids={999},
            )
        assert result.simulated is False
        assert "STALE ALLOW-LIST" not in result.detail

    def test_stale_gate_does_not_affect_passive(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="passive",
            state_dir=tmp_path,
            allow_list_max_age=1.0,
        )
        mgr.update("passive", allow_list=["something"])
        enforcer = Enforcer(posture_manager=mgr)

        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 10.0

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="NewTool",
            tool_class="C",
            pids={999},
        )
        # Passive mode returns log_and_alert regardless of staleness
        assert result.tactic == "log_and_alert"
        assert result.simulated is False
        assert "STALE" not in result.detail

    def test_stale_gate_does_not_affect_audit(self, tmp_path: Path) -> None:
        mgr = PostureManager(
            initial_posture="audit",
            state_dir=tmp_path,
            allow_list_max_age=1.0,
        )
        mgr.update("audit", allow_list=["something"])
        enforcer = Enforcer(posture_manager=mgr)

        with mgr._lock:
            mgr._allow_list_synced_at = time.monotonic() - 10.0

        result = enforcer.enforce(
            decision=_make_decision("block"),
            tool_name="NewTool",
            tool_class="C",
            pids={999},
        )
        # Audit mode simulates normally, staleness gate is for active only
        assert result.simulated is True
        assert "STALE" not in result.detail
