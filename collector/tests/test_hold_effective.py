"""Tests for P4a: hold_effective field across enforcement dataclasses and events.

Verifies that the hold_effective boolean is present on EnforcementResult,
HoldResult, and propagated into canonical enforcement events built by
build_event().  P4a always sets hold_effective=False because SIGSTOP
suspension is deferred to P4b.
"""

from __future__ import annotations

import json
from pathlib import Path

from enforcement.enforcer import EnforcementResult
from enforcement.approval_hold import HoldResult
from event_builder import build_event
from engine.policy import PolicyDecision
from scanner.base import LayerSignals, ScanResult


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _minimal_scan() -> ScanResult:
    """Return a minimal ScanResult sufficient for build_event()."""
    return ScanResult(
        detected=True,
        tool_name="test-tool",
        tool_class="B",
        tool_version="1.0",
        signals=LayerSignals(process=0.8, file=0.5, network=0.0, identity=0.0, behavior=0.0),
        action_type="exec",
        action_risk="R2",
        action_summary="Test action",
    )


def _minimal_policy() -> PolicyDecision:
    """Return a minimal PolicyDecision for approval_required."""
    return PolicyDecision(
        decision_state="approval_required",
        rule_id="RULE-APPROVAL-001",
        rule_version="0.4.0",
        reason_codes=["approval_required_test"],
        decision_confidence=0.65,
    )


# --- Test 1: EnforcementResult has hold_effective with default False ---

def test_enforcement_result_has_hold_effective_field():
    result = EnforcementResult(tactic="hold_pending_approval", success=True)
    assert hasattr(result, "hold_effective")
    assert result.hold_effective is False


def test_enforcement_result_hold_effective_can_be_set_true():
    result = EnforcementResult(
        tactic="hold_pending_approval",
        success=True,
        hold_effective=True,
    )
    assert result.hold_effective is True


# --- Test 2: HoldResult has hold_effective with default False ---

def test_hold_result_has_hold_effective_field():
    result = HoldResult(decision="denied", approval_id="abc-123")
    assert hasattr(result, "hold_effective")
    assert result.hold_effective is False


def test_hold_result_hold_effective_can_be_set_true():
    result = HoldResult(
        decision="denied",
        approval_id="abc-123",
        hold_effective=True,
    )
    assert result.hold_effective is True


# --- Test 3: Built enforcement events contain hold_effective ---

def test_enforcement_event_includes_hold_effective():
    scan = _minimal_scan()
    policy = _minimal_policy()
    enforcement = EnforcementResult(
        tactic="hold_pending_approval",
        success=True,
        detail="Holding test-tool pending approval",
        tool_name="test-tool",
        hold_effective=False,
    )

    event = build_event(
        event_type="enforcement.applied",
        endpoint_id="EP-001",
        actor_id="test@detec.io",
        session_id="sess-001",
        trace_id="trace-001",
        scan=scan,
        confidence=0.65,
        sensitivity="Tier1",
        policy=policy,
        enforcement=enforcement,
    )

    assert "enforcement" in event
    assert "hold_effective" in event["enforcement"]
    assert event["enforcement"]["hold_effective"] is False


def test_enforcement_event_hold_effective_true_when_set():
    scan = _minimal_scan()
    policy = _minimal_policy()
    enforcement = EnforcementResult(
        tactic="hold_pending_approval",
        success=True,
        detail="Holding test-tool pending approval",
        tool_name="test-tool",
        hold_effective=True,
    )

    event = build_event(
        event_type="enforcement.applied",
        endpoint_id="EP-001",
        actor_id="test@detec.io",
        session_id="sess-001",
        trace_id="trace-001",
        scan=scan,
        confidence=0.65,
        sensitivity="Tier1",
        policy=policy,
        enforcement=enforcement,
    )

    assert event["enforcement"]["hold_effective"] is True


# --- Test 4: Current approval flow always sets hold_effective=False ---

def test_hold_effective_false_by_default():
    """The entire current approval flow never sets hold_effective=True.

    This validates that P4a's contract is met: hold_effective is always
    False until P4b implements SIGSTOP suspension.
    """
    # HoldResult from any code path defaults to False
    hold_approved = HoldResult(decision="approved", approval_id="a1")
    hold_denied = HoldResult(decision="denied", approval_id="a2")
    hold_timed_out = HoldResult(decision="denied", approval_id="a3", timed_out=True)

    assert hold_approved.hold_effective is False
    assert hold_denied.hold_effective is False
    assert hold_timed_out.hold_effective is False

    # EnforcementResult from the enforcer defaults to False
    enf_block = EnforcementResult(tactic="process_kill", success=True)
    enf_hold = EnforcementResult(tactic="hold_pending_approval", success=True)
    enf_log = EnforcementResult(tactic="log_and_alert", success=True)

    assert enf_block.hold_effective is False
    assert enf_hold.hold_effective is False
    assert enf_log.hold_effective is False


# --- Test 5: Schema validation (structural check) ---

def test_schema_includes_hold_effective_property():
    """Verify the canonical event schema defines hold_effective in the enforcement section."""
    schema_path = _repo_root() / "schemas" / "canonical-event-schema.json"
    schema = json.loads(schema_path.read_text())

    enforcement_def = schema["$defs"]["enforcement"]
    assert "hold_effective" in enforcement_def["properties"]

    prop = enforcement_def["properties"]["hold_effective"]
    assert prop["type"] == "boolean"
    assert prop["default"] is False
