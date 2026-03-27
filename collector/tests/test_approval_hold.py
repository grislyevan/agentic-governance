# collector/tests/test_approval_hold.py
from unittest.mock import MagicMock, patch, call
import pytest
import requests
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


# --- Fix 1: timeout_seconds=0 still makes exactly one poll attempt ---

def test_timeout_zero_makes_one_poll_attempt():
    """timeout_seconds=0 must still poll once before timing out."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=0, timeout_behavior="deny")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_calls = []
    def _fake_poll(approval_id):
        poll_calls.append(approval_id)
        return "pending"

    with patch.object(manager, "_create_approval_request", return_value="ar-zero"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-zero", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-0",
        )

    assert len(poll_calls) == 1, f"Expected exactly 1 poll, got {len(poll_calls)}"
    assert result.timed_out is True
    assert result.decision == "denied"


# --- Fix 3: HoldConfig raises ValueError on invalid behavior values ---

def test_holdconfig_rejects_invalid_timeout_behavior():
    """HoldConfig must raise ValueError for unrecognised timeout_behavior."""
    with pytest.raises(ValueError, match="timeout_behavior"):
        HoldConfig(timeout_behavior="dny")


def test_holdconfig_rejects_invalid_offline_behavior():
    """HoldConfig must raise ValueError for unrecognised offline_behavior."""
    with pytest.raises(ValueError, match="offline_behavior"):
        HoldConfig(offline_behavior="grant")


def test_holdconfig_from_dict_rejects_invalid_behavior():
    """HoldConfig.from_dict must also raise ValueError for unrecognised values."""
    with pytest.raises(ValueError, match="timeout_behavior"):
        HoldConfig.from_dict({"timeout_behavior": "ALLOW"})


# --- Fix 4: 401 during polling returns denied immediately, no retry ---

# --- Fix: _normalize_decision handles all 4 valid behavior values ---

@pytest.mark.parametrize("behavior,expected", [
    ("deny", "denied"),
    ("denied", "denied"),
    ("approve", "approved"),
    ("approved", "approved"),
])
def test_normalize_decision_all_valid_values(behavior, expected):
    """_normalize_decision must map all 4 valid behavior strings correctly."""
    from enforcement.approval_hold import _normalize_decision
    assert _normalize_decision(behavior) == expected


def test_timeout_behavior_denied_string_returns_denied():
    """timeout_behavior='denied' must yield a denied HoldResult (not approved)."""
    config = HoldConfig(poll_interval_seconds=0, timeout_seconds=0, timeout_behavior="denied")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", return_value="ar-td"), \
         patch.object(manager, "_poll_decision", return_value="pending"), \
         patch("enforcement.approval_hold.time.sleep"):
        result = manager.wait_for_decision(
            event_id="evt-td", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-td",
        )

    assert result.decision == "denied", (
        f"Expected 'denied' but got '{result.decision}' — _normalize_decision bug"
    )
    assert result.timed_out is True


def test_offline_behavior_approved_string_returns_approved():
    """offline_behavior='approved' must yield an approved HoldResult."""
    config = HoldConfig(offline_behavior="approved")
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    with patch.object(manager, "_create_approval_request", side_effect=Exception("offline")):
        result = manager.wait_for_decision(
            event_id="evt-oa", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-oa",
        )

    assert result.decision == "approved"
    assert result.timed_out is False


def test_poll_401_returns_denied_immediately():
    """A 401 response during polling must return denied without sleeping/retrying."""
    config = HoldConfig(poll_interval_seconds=60, timeout_seconds=300)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    sleep_calls = []
    with patch.object(manager, "_create_approval_request", return_value="ar-401"), \
         patch("requests.get", return_value=mock_resp), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_calls.append(s)):
        result = manager.wait_for_decision(
            event_id="evt-401", tool_name="tool", tool_class="B",
            confidence_band="high", confidence_score=0.8, policy_rule_id="R-1",
        )

    assert result.decision == "denied"
    assert result.timed_out is False
    assert len(sleep_calls) == 0, "Should not sleep on non-transient 4xx error"


# --- Exponential backoff with jitter tests ---

def test_backoff_delays_increase_exponentially():
    """Sleep durations must follow exponential backoff pattern (with jitter in bounds)."""
    config = HoldConfig(poll_interval_seconds=2, max_poll_interval_seconds=60, timeout_seconds=600)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_count = 0
    def _fake_poll(approval_id):
        nonlocal poll_count
        poll_count += 1
        if poll_count < 6:
            return "pending"
        return "approved"

    sleep_durations = []
    with patch.object(manager, "_create_approval_request", return_value="ar-bo"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_durations.append(s)), \
         patch("enforcement.approval_hold.random.random", return_value=0.5):
        result = manager.wait_for_decision(
            event_id="evt-bo", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-bo",
        )

    assert result.decision == "approved"
    # With random.random()=0.5, jitter multiplier is 0.5 + 0.5*0.5 = 0.75
    # attempt 0: min(2*2^0, 60) * 0.75 = 2 * 0.75 = 1.5
    # attempt 1: min(2*2^1, 60) * 0.75 = 4 * 0.75 = 3.0
    # attempt 2: min(2*2^2, 60) * 0.75 = 8 * 0.75 = 6.0
    # attempt 3: min(2*2^3, 60) * 0.75 = 16 * 0.75 = 12.0
    # attempt 4: min(2*2^4, 60) * 0.75 = 32 * 0.75 = 24.0
    assert len(sleep_durations) == 5  # 5 "pending" polls, then "approved" on 6th
    assert sleep_durations == pytest.approx([1.5, 3.0, 6.0, 12.0, 24.0])


def test_backoff_capped_at_max_poll_interval():
    """Backoff delay must never exceed max_poll_interval_seconds (before jitter)."""
    config = HoldConfig(poll_interval_seconds=10, max_poll_interval_seconds=30, timeout_seconds=600)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_count = 0
    def _fake_poll(approval_id):
        nonlocal poll_count
        poll_count += 1
        if poll_count < 5:
            return "pending"
        return "approved"

    sleep_durations = []
    with patch.object(manager, "_create_approval_request", return_value="ar-cap"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_durations.append(s)), \
         patch("enforcement.approval_hold.random.random", return_value=1.0):
        # random.random()=1.0 => jitter multiplier = 0.5 + 1.0*0.5 = 1.0 (no reduction)
        result = manager.wait_for_decision(
            event_id="evt-cap", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-cap",
        )

    assert result.decision == "approved"
    # attempt 0: min(10*1, 30) * 1.0 = 10
    # attempt 1: min(10*2, 30) * 1.0 = 20
    # attempt 2: min(10*4, 30) * 1.0 = 30  (capped)
    # attempt 3: min(10*8, 30) * 1.0 = 30  (capped)
    assert len(sleep_durations) == 4
    assert sleep_durations == pytest.approx([10.0, 20.0, 30.0, 30.0])


def test_backoff_jitter_bounds():
    """With jitter, delay must be between raw_delay*0.5 and raw_delay*1.0."""
    config = HoldConfig(poll_interval_seconds=4, max_poll_interval_seconds=60, timeout_seconds=600)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_count = 0
    def _fake_poll(approval_id):
        nonlocal poll_count
        poll_count += 1
        if poll_count < 2:
            return "pending"
        return "approved"

    # Test with minimum jitter: random.random()=0.0 => multiplier=0.5
    sleep_durations = []
    with patch.object(manager, "_create_approval_request", return_value="ar-jl"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_durations.append(s)), \
         patch("enforcement.approval_hold.random.random", return_value=0.0):
        manager.wait_for_decision(
            event_id="evt-jl", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-jl",
        )

    # attempt 0: min(4*1, 60) * (0.5 + 0.0*0.5) = 4 * 0.5 = 2.0
    assert len(sleep_durations) == 1
    assert sleep_durations[0] == pytest.approx(2.0)


def test_backoff_on_request_exception():
    """Request exceptions should also trigger backoff (not fixed interval)."""
    config = HoldConfig(poll_interval_seconds=5, max_poll_interval_seconds=60, timeout_seconds=600)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_count = 0
    def _failing_poll(approval_id):
        nonlocal poll_count
        poll_count += 1
        if poll_count <= 2:
            raise requests.exceptions.ConnectionError("connection refused")
        return "approved"

    sleep_durations = []
    with patch.object(manager, "_create_approval_request", return_value="ar-err"), \
         patch.object(manager, "_poll_decision", side_effect=_failing_poll), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_durations.append(s)), \
         patch("enforcement.approval_hold.random.random", return_value=0.5):
        result = manager.wait_for_decision(
            event_id="evt-err", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-err",
        )

    assert result.decision == "approved"
    # Two exceptions trigger two sleeps; third call succeeds immediately
    # jitter multiplier = 0.75
    # attempt 0: min(5*1, 60) * 0.75 = 3.75
    # attempt 1: min(5*2, 60) * 0.75 = 7.5
    assert len(sleep_durations) == 2
    assert sleep_durations == pytest.approx([3.75, 7.5])


def test_holdconfig_max_poll_interval_default():
    """HoldConfig default max_poll_interval_seconds is 60."""
    cfg = HoldConfig()
    assert cfg.max_poll_interval_seconds == 60


def test_holdconfig_from_dict_max_poll_interval():
    """HoldConfig.from_dict parses max_poll_interval_seconds."""
    cfg = HoldConfig.from_dict({"max_poll_interval_seconds": 30})
    assert cfg.max_poll_interval_seconds == 30


def test_backoff_zero_base_interval():
    """With poll_interval_seconds=0, all delays are 0 (no thundering herd possible)."""
    config = HoldConfig(poll_interval_seconds=0, max_poll_interval_seconds=60, timeout_seconds=10)
    manager = ApprovalHoldManager(api_url="http://localhost:8000/api", api_key="k", config=config)

    poll_count = 0
    def _fake_poll(approval_id):
        nonlocal poll_count
        poll_count += 1
        if poll_count < 3:
            return "pending"
        return "denied"

    sleep_durations = []
    with patch.object(manager, "_create_approval_request", return_value="ar-z"), \
         patch.object(manager, "_poll_decision", side_effect=_fake_poll), \
         patch("enforcement.approval_hold.time.sleep", side_effect=lambda s: sleep_durations.append(s)):
        result = manager.wait_for_decision(
            event_id="evt-z", tool_name="tool", tool_class="A",
            confidence_band="low", confidence_score=0.1, policy_rule_id="R-z",
        )

    assert result.decision == "denied"
    assert len(sleep_durations) == 2
    # 0 * anything = 0
    assert all(d == 0.0 for d in sleep_durations)
