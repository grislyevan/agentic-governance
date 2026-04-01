"""Tests for resurrection escalation safety gate.

Covers:
  - Protected parent blocklist prevents parent process kills
  - Unprotected parent still allows escalation
  - Persistent service disable gated behind allow_persistent_disable
  - Corroboration requirement for resurrection escalation
  - Custom protected parents loaded from config
"""

from __future__ import annotations

import platform
from pathlib import Path
from unittest import mock

import pytest

from enforcement.enforcer import Enforcer, EnforcementResult, PROTECTED_PARENTS
from enforcement.process_kill import KillResult
from engine.policy import PolicyDecision


def _make_decision(state: str = "block", confidence: float = 0.85) -> PolicyDecision:
    return PolicyDecision(
        decision_state=state,
        rule_id="ENFORCE-004",
        rule_version="0.4.0",
        reason_codes=["test"],
        decision_confidence=confidence,
    )


def _make_enforcer(
    tmp_path: Path,
    *,
    protected_parents: set[str] | None = None,
    allow_persistent_disable: bool = False,
    require_corroboration: bool = False,
) -> Enforcer:
    """Create an active-posture Enforcer with safety gate parameters."""
    from enforcement.posture import PostureManager

    mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
    return Enforcer(
        posture_manager=mgr,
        max_enforcements_per_minute=20,
        protected_parents=protected_parents,
        allow_persistent_disable=allow_persistent_disable,
        require_corroboration=require_corroboration,
    )


def _trigger_resurrection(enforcer: Enforcer, tool_name: str = "BadAgent", **kwargs) -> EnforcementResult:
    """Fire 3 block enforcements to trigger resurrection escalation.

    Returns the result of the third enforcement (the one that escalates).
    """
    result = None
    with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
        m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

        for _ in range(3):
            result = enforcer.enforce(
                decision=_make_decision("block"),
                tool_name=tool_name,
                tool_class="C",
                pids={999},
                **kwargs,
            )
    return result  # type: ignore[return-value]


# -- Protected parent tests ---------------------------------------------------


class TestProtectedParentBlocksEscalation:
    """Verify that protected parent processes are never killed during escalation."""

    def test_protected_parent_blocks_escalation(self, tmp_path: Path) -> None:
        """When the parent process is 'bash', parent kill is skipped."""
        enforcer = _make_enforcer(tmp_path)

        mock_parent = mock.Mock()
        mock_parent.name.return_value = "bash"

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 500
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            # Mock psutil.Process to return different objects for target vs parent
            def _mock_process(pid):
                if pid == 500:
                    return mock_parent
                return mock_target

            with mock.patch("psutil.Process", side_effect=_mock_process):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                    )

        assert result.escalated is True
        # The parent kill should have been skipped
        assert any("protected" in d for d in result.escalation_details)
        # kill_process_tree should NOT have been called with parent PID 500
        parent_kill_calls = [c for c in m_kill.call_args_list if c[0][0] == 500]
        assert len(parent_kill_calls) == 0

    @pytest.mark.parametrize("parent_name", [
        "bash", "zsh", "code", "Cursor", "iTerm2", "tmux",
        "WindowServer", "launchd", "systemd", "init", "sshd",
        "gnome-terminal", "explorer.exe",
    ])
    def test_various_protected_parents(self, tmp_path: Path, parent_name: str) -> None:
        """All names in PROTECTED_PARENTS block parent kill."""
        assert parent_name in PROTECTED_PARENTS

    def test_default_protected_parents_is_frozenset(self) -> None:
        """PROTECTED_PARENTS is immutable."""
        assert isinstance(PROTECTED_PARENTS, frozenset)
        assert len(PROTECTED_PARENTS) > 0


class TestUnprotectedParentAllowsEscalation:
    """Verify that non-protected parent processes can still be killed."""

    def test_unprotected_parent_allows_escalation(self, tmp_path: Path) -> None:
        """When the parent process is 'custom-agent', parent kill proceeds."""
        enforcer = _make_enforcer(tmp_path)

        mock_parent = mock.Mock()
        mock_parent.name.return_value = "custom-agent"

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 500
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            def _mock_process(pid):
                if pid == 500:
                    return mock_parent
                return mock_target

            with mock.patch("psutil.Process", side_effect=_mock_process):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                    )

        assert result.escalated is True
        # The parent kill SHOULD have been called for PID 500
        parent_kill_calls = [c for c in m_kill.call_args_list if c[0][0] == 500]
        assert len(parent_kill_calls) == 1
        assert any("killed parent" in d for d in result.escalation_details)


# -- Persistent disable gate tests -------------------------------------------


class TestPersistentDisableGate:
    """Verify that systemctl/launchctl calls are gated by allow_persistent_disable."""

    def test_persistent_disable_skipped_by_default(self, tmp_path: Path) -> None:
        """When allow_persistent_disable is False (default), systemctl/launchctl not called."""
        enforcer = _make_enforcer(tmp_path, allow_persistent_disable=False)

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 1  # no parent to kill
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("psutil.Process", return_value=mock_target):
                with mock.patch("subprocess.run") as m_subprocess:
                    for _ in range(3):
                        result = enforcer.enforce(
                            decision=_make_decision("block"),
                            tool_name="BadAgent",
                            tool_class="C",
                            pids={999},
                        )

        assert result.escalated is True
        # subprocess.run should NOT have been called for systemctl/launchctl
        m_subprocess.assert_not_called()
        assert any("persistent disable skipped" in d for d in result.escalation_details)

    def test_persistent_disable_allowed_when_enabled(self, tmp_path: Path) -> None:
        """When allow_persistent_disable is True, systemctl/launchctl calls proceed."""
        enforcer = _make_enforcer(tmp_path, allow_persistent_disable=True)

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 1  # no parent to kill
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("psutil.Process", return_value=mock_target):
                with mock.patch("platform.system", return_value="Linux"):
                    with mock.patch("builtins.open", mock.mock_open(
                        read_data="0::/system.slice/bad-agent.service\n"
                    )):
                        with mock.patch("subprocess.run") as m_subprocess:
                            m_subprocess.return_value = mock.Mock(returncode=0)
                            for _ in range(3):
                                result = enforcer.enforce(
                                    decision=_make_decision("block"),
                                    tool_name="BadAgent",
                                    tool_class="C",
                                    pids={999},
                                )

        assert result.escalated is True
        # systemctl disable --now should have been called
        m_subprocess.assert_called()
        assert any("disabled unit" in d for d in result.escalation_details)


# -- Corroboration requirement tests ------------------------------------------


class TestCorroborationRequired:
    """Verify resurrection only escalates with 2+ independent scanners."""

    def test_corroboration_required_single_scanner_no_escalation(self, tmp_path: Path) -> None:
        """With require_corroboration=True and only 1 scanner, no escalation."""
        enforcer = _make_enforcer(tmp_path, require_corroboration=True)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            for _ in range(3):
                result = enforcer.enforce(
                    decision=_make_decision("block"),
                    tool_name="BadAgent",
                    tool_class="C",
                    pids={999},
                    corroborating_scanners={"CursorScanner"},
                )

        # Should NOT escalate because only 1 scanner corroborated
        assert result.escalated is False

    def test_corroboration_required_two_scanners_escalates(self, tmp_path: Path) -> None:
        """With require_corroboration=True and 2 scanners, escalation proceeds."""
        enforcer = _make_enforcer(tmp_path, require_corroboration=True)

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 1
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("psutil.Process", return_value=mock_target):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                        corroborating_scanners={"CursorScanner", "BehavioralScanner"},
                    )

        assert result.escalated is True

    def test_corroboration_not_required_single_scanner_escalates(self, tmp_path: Path) -> None:
        """With require_corroboration=False, single scanner still triggers escalation."""
        enforcer = _make_enforcer(tmp_path, require_corroboration=False)

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 1
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("psutil.Process", return_value=mock_target):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                        corroborating_scanners={"CursorScanner"},
                    )

        assert result.escalated is True

    def test_corroboration_none_scanners_ignores_gate(self, tmp_path: Path) -> None:
        """When corroborating_scanners is None, corroboration gate is skipped."""
        enforcer = _make_enforcer(tmp_path, require_corroboration=True)

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 1
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            with mock.patch("psutil.Process", return_value=mock_target):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                        # corroborating_scanners not provided (None)
                    )

        # Should still escalate because corroborating_scanners is None
        assert result.escalated is True

    def test_corroboration_empty_set_blocks_escalation(self, tmp_path: Path) -> None:
        """When corroborating_scanners is empty set, escalation is blocked."""
        enforcer = _make_enforcer(tmp_path, require_corroboration=True)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            for _ in range(3):
                result = enforcer.enforce(
                    decision=_make_decision("block"),
                    tool_name="BadAgent",
                    tool_class="C",
                    pids={999},
                    corroborating_scanners=set(),
                )

        assert result.escalated is False


# -- Custom protected parents from config tests --------------------------------


class TestCustomProtectedParentsFromConfig:
    """Verify config-loaded parents are added to default set."""

    def test_custom_protected_parents_from_config(self, tmp_path: Path) -> None:
        """Custom parents passed via config extend the default set."""
        enforcer = _make_enforcer(
            tmp_path,
            protected_parents={"my-custom-terminal", "my-ide"},
        )

        # Verify default parents are still present
        assert "bash" in enforcer._protected_parents
        assert "zsh" in enforcer._protected_parents
        assert "code" in enforcer._protected_parents

        # Verify custom parents were added
        assert "my-custom-terminal" in enforcer._protected_parents
        assert "my-ide" in enforcer._protected_parents

    def test_no_custom_parents_uses_defaults_only(self, tmp_path: Path) -> None:
        """When no custom parents provided, only defaults are used."""
        enforcer = _make_enforcer(tmp_path)
        assert enforcer._protected_parents == PROTECTED_PARENTS

    def test_custom_parent_blocks_escalation(self, tmp_path: Path) -> None:
        """A custom-added parent name blocks parent kill during escalation."""
        enforcer = _make_enforcer(
            tmp_path,
            protected_parents={"my-custom-terminal"},
        )

        mock_parent = mock.Mock()
        mock_parent.name.return_value = "my-custom-terminal"

        mock_target = mock.Mock()
        mock_target.ppid.return_value = 500
        mock_target.exe.return_value = "/usr/bin/bad-agent"

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            def _mock_process(pid):
                if pid == 500:
                    return mock_parent
                return mock_target

            with mock.patch("psutil.Process", side_effect=_mock_process):
                for _ in range(3):
                    result = enforcer.enforce(
                        decision=_make_decision("block"),
                        tool_name="BadAgent",
                        tool_class="C",
                        pids={999},
                    )

        assert result.escalated is True
        assert any("protected" in d for d in result.escalation_details)
        # Parent PID 500 should NOT have been killed
        parent_kill_calls = [c for c in m_kill.call_args_list if c[0][0] == 500]
        assert len(parent_kill_calls) == 0


# -- Config loader integration tests ------------------------------------------


class TestConfigLoaderEnforcement:
    """Verify config_loader properly loads enforcement config keys."""

    def test_enforcement_defaults_in_config(self, tmp_path: Path) -> None:
        """Default enforcement config is present in loaded config."""
        import json

        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps({}))

        from config_loader import load_collector_config
        cfg = load_collector_config(config_file)

        assert "enforcement" in cfg
        assert cfg["enforcement"]["allow_persistent_disable"] is False
        assert cfg["enforcement"]["require_corroboration"] is True
        assert cfg["enforcement"]["protected_parents"] == []

    def test_enforcement_config_from_file(self, tmp_path: Path) -> None:
        """Enforcement config from JSON file overrides defaults."""
        import json

        config_data = {
            "enforcement": {
                "protected_parents": ["my-custom-shell"],
                "allow_persistent_disable": True,
                "require_corroboration": False,
            }
        }
        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps(config_data))

        from config_loader import load_collector_config
        cfg = load_collector_config(config_file)

        assert cfg["enforcement"]["protected_parents"] == ["my-custom-shell"]
        assert cfg["enforcement"]["allow_persistent_disable"] is True
        assert cfg["enforcement"]["require_corroboration"] is False

    def test_enforcement_partial_config_merges(self, tmp_path: Path) -> None:
        """Partial enforcement config merges with defaults."""
        import json

        config_data = {
            "enforcement": {
                "allow_persistent_disable": True,
            }
        }
        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps(config_data))

        from config_loader import load_collector_config
        cfg = load_collector_config(config_file)

        # Overridden value
        assert cfg["enforcement"]["allow_persistent_disable"] is True
        # Defaults preserved
        assert cfg["enforcement"]["require_corroboration"] is True
        assert cfg["enforcement"]["protected_parents"] == []

    def test_enforcement_env_override(self, tmp_path: Path) -> None:
        """Environment variables override enforcement config."""
        import json

        config_file = tmp_path / "collector.json"
        config_file.write_text(json.dumps({}))

        from config_loader import load_collector_config
        with mock.patch.dict("os.environ", {
            "AGENTIC_GOV_ENFORCEMENT_ALLOW_PERSISTENT_DISABLE": "true",
            "AGENTIC_GOV_ENFORCEMENT_REQUIRE_CORROBORATION": "false",
        }):
            cfg = load_collector_config(config_file)

        assert cfg["enforcement"]["allow_persistent_disable"] is True
        assert cfg["enforcement"]["require_corroboration"] is False


# -- Backward compatibility tests ---------------------------------------------


class TestBackwardCompatibility:
    """Verify that existing behavior is preserved when no new config is provided."""

    def test_default_enforcer_has_safe_defaults(self, tmp_path: Path) -> None:
        """Enforcer with no safety-gate args defaults to safe values."""
        from enforcement.posture import PostureManager

        mgr = PostureManager(initial_posture="active", state_dir=tmp_path)
        enforcer = Enforcer(posture_manager=mgr)

        assert enforcer._protected_parents == PROTECTED_PARENTS
        assert enforcer._allow_persistent_disable is False
        assert enforcer._require_corroboration is False

    def test_resurrection_still_detected(self, tmp_path: Path) -> None:
        """Resurrection detection still works (kill history tracking)."""
        enforcer = _make_enforcer(tmp_path)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            results = []
            for _ in range(3):
                r = enforcer.enforce(
                    decision=_make_decision("block"),
                    tool_name="BadAgent",
                    tool_class="C",
                    pids={999},
                )
                results.append(r)

        assert results[0].escalated is False
        assert results[1].escalated is False
        assert results[2].escalated is True

    def test_first_kill_never_escalated(self, tmp_path: Path) -> None:
        """Single kill never triggers escalation (unchanged behavior)."""
        enforcer = _make_enforcer(tmp_path)

        with mock.patch("enforcement.process_kill.kill_process_tree") as m_kill:
            m_kill.return_value = KillResult(pid=999, success=True, killed_pids=[999], detail="killed")

            result = enforcer.enforce(
                decision=_make_decision("block"),
                tool_name="BadAgent",
                tool_class="C",
                pids={999},
            )

        assert result.escalated is False
