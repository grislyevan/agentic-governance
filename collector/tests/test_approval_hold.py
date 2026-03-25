# collector/tests/test_approval_hold.py
from unittest.mock import MagicMock, patch
import pytest
from enforcement.approval_hold import ApprovalHoldManager, HoldConfig, HoldResult


def test_hold_config_defaults():
    cfg = HoldConfig()
    assert cfg.poll_interval_seconds == 10
    assert cfg.timeout_seconds == 300
    assert cfg.timeout_behavior == "deny"
    assert cfg.offline_behavior == "deny"


def test_hold_result_approved():
    result = HoldResult(decision="approved", approval_id="abc")
    assert result.decision == "approved"
    assert not result.timed_out


def test_hold_result_timed_out():
    result = HoldResult(decision="denied", approval_id=None, timed_out=True)
    assert result.timed_out


def test_hold_config_from_dict():
    cfg = HoldConfig.from_dict({
        "poll_interval_seconds": 5,
        "timeout_seconds": 60,
        "timeout_behavior": "approve",
        "offline_behavior": "deny",
    })
    assert cfg.poll_interval_seconds == 5
    assert cfg.timeout_seconds == 60
    assert cfg.timeout_behavior == "approve"


def test_manager_offline_returns_deny_when_create_fails():
    """When POST /approvals fails (offline), offline_behavior=deny returns denied."""
    config = HoldConfig(offline_behavior="deny")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", side_effect=Exception("conn refused")):
        result = manager.wait_for_decision(
            event_id="evt-1", tool_name="cursor", tool_class="B",
            confidence_band="medium", confidence_score=0.6, policy_rule_id="RULE-3",
        )

    assert result.decision == "denied"
    assert result.timed_out is False


def test_manager_returns_approved_after_polling():
    """When server returns approved on second poll, decision is approved."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=10)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    call_count = 0
    def _fake_poll(approval_id):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "pending"
        return "approved"

    with patch.object(manager, "_create_approval_request", return_value="ar-99"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-2", tool_name="claude_code", tool_class="D",
            confidence_band="high", confidence_score=0.9, policy_rule_id="D01",
        )

    assert result.decision == "approved"
    assert result.approval_id == "ar-99"
    assert call_count == 2


def test_manager_timeout_returns_configured_behavior():
    """Timeout returns timeout_behavior decision."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=0, timeout_behavior="deny")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", return_value="ar-1"), \
         patch.object(manager, "_poll_decision", return_value="pending"), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-3", tool_name="x", tool_class="A",
            confidence_band="low", confidence_score=0.3, policy_rule_id="RULE-1",
        )

    assert result.decision == "denied"
    assert result.timed_out is True
