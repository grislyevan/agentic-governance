"""Tests for enforcement posture manager and posture-aware enforcer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
_COLLECTOR_DIR = str(Path(__file__).resolve().parent.parent)
if _COLLECTOR_DIR not in sys.path:
    sys.path.insert(0, _COLLECTOR_DIR)

from enforcement.posture import PostureManager
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
