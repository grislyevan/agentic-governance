"""Tests for probe subsystem: triggers, budget, state machine, engine."""

from __future__ import annotations

from datetime import datetime, timezone
from probe.budget import TriggerBudget
from probe.engine import ProbeEngine
from probe.models import ProbeDelta, TriggerContext
from probe.models import VigilanceContext
from probe.state_machine import (
    create_idle,
    transition_to_cooldown,
    transition_to_elevated,
    transition_to_idle_from_cooldown,
    transition_to_observing,
)
from probe.triggers import evaluate_triggers
from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)


def test_trigger_budget_allow_trigger_cooldown() -> None:
    now = datetime.now(timezone.utc)
    budget = TriggerBudget(cooldown_seconds=10, max_alert_scans_per_minute=4)
    allowed, _ = budget.allow_trigger("ai_tool_process_start", now)
    assert allowed is True
    allowed2, suppressed = budget.allow_trigger("ai_tool_process_start", now)
    assert allowed2 is False
    assert suppressed >= 1


def test_trigger_budget_allow_scan() -> None:
    budget = TriggerBudget(max_alert_scans_per_minute=2)
    assert budget.allow_scan() is True
    budget.record_scan()
    budget.record_scan()
    assert budget.allow_scan() is False


def test_evaluate_triggers_agentic_process() -> None:
    now = datetime.now(timezone.utc)
    delta = ProbeDelta(
        ts=now,
        source="polling",
        process_events=[
            ProcessExecEvent(
                timestamp=now,
                pid=1,
                ppid=0,
                name="cursor",
                cmdline="cursor",
                source="polling",
            ),
        ],
        file_events=[],
        network_events=[],
    )
    matches = evaluate_triggers(delta)
    assert any(m.trigger_type == "ai_tool_process_start" for m in matches)


def test_evaluate_triggers_llm_endpoint() -> None:
    now = datetime.now(timezone.utc)
    delta = ProbeDelta(
        ts=now,
        source="polling",
        process_events=[],
        file_events=[],
        network_events=[
            NetworkConnectEvent(
                timestamp=now,
                pid=1,
                process_name="curl",
                remote_addr="api.anthropic.com",
                remote_port=443,
                local_port=0,
                source="polling",
            ),
        ],
    )
    matches = evaluate_triggers(delta)
    assert any(m.trigger_type == "outbound_llm_endpoint" for m in matches)


def test_state_machine_transitions() -> None:
    ctx = create_idle("ep-1")
    assert ctx.state == "IDLE"
    ctx2 = transition_to_observing(ctx, 120)
    assert ctx2.state == "OBSERVING"
    assert ctx2.observation_expires_at is not None
    ctx3 = transition_to_elevated(ctx2)
    assert ctx3.state == "ELEVATED"
    ctx4 = transition_to_cooldown(ctx3, 10)
    assert ctx4.state == "COOLDOWN"
    assert ctx4.cooldown_expires_at is not None
    idle_again = transition_to_idle_from_cooldown(ctx4)
    assert idle_again is None  # not expired yet
    from datetime import timedelta
    past = datetime.now(timezone.utc) + timedelta(seconds=30)
    ctx_expired = VigilanceContext(
        endpoint_id=ctx4.endpoint_id,
        tool=ctx4.tool,
        state="COOLDOWN",
        state_since=ctx4.state_since,
        observation_expires_at=None,
        cooldown_expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        trigger_budget_window_start=ctx4.trigger_budget_window_start,
        alert_triggered_scans_in_window=ctx4.alert_triggered_scans_in_window,
    )
    idle_after = transition_to_idle_from_cooldown(ctx_expired, now=past)
    assert idle_after is not None
    assert idle_after.state == "IDLE"


def test_probe_engine_push_delta_calls_on_request_scan() -> None:
    requested: list[TriggerContext] = []
    engine = ProbeEngine(
        endpoint_id="ep-1",
        cooldown_seconds=0,
        max_alert_scans_per_minute=10,
        on_request_scan=requested.append,
    )
    now = datetime.now(timezone.utc)
    delta = ProbeDelta(
        ts=now,
        source="polling",
        process_events=[
            ProcessExecEvent(
                timestamp=now,
                pid=1,
                ppid=0,
                name="cursor",
                cmdline="cursor",
                source="polling",
            ),
        ],
        file_events=[],
        network_events=[],
    )
    engine.push_delta(delta)
    assert len(requested) == 1
    assert requested[0].scan_reason == "alert"
    assert requested[0].trigger_type == "ai_tool_process_start"
