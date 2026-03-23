"""Vigilance state machine: IDLE, OBSERVING, ELEVATED, COOLDOWN."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from probe.models import VigilanceContext, VigilanceState


def create_idle(
    endpoint_id: str,
    tool: str | None = None,
    now: datetime | None = None,
) -> VigilanceContext:
    """Create a new context in IDLE state."""
    now = now or datetime.now(timezone.utc)
    return VigilanceContext(
        endpoint_id=endpoint_id,
        tool=tool,
        state="IDLE",
        state_since=now,
        observation_expires_at=None,
        cooldown_expires_at=None,
        trigger_budget_window_start=now,
        alert_triggered_scans_in_window=0,
    )


def transition_to_observing(
    ctx: VigilanceContext,
    observation_window_seconds: int,
    now: datetime | None = None,
) -> VigilanceContext:
    """IDLE or COOLDOWN -> OBSERVING on weak/moderate trigger. Sets observation_expires_at."""
    now = now or datetime.now(timezone.utc)
    from datetime import timedelta
    return VigilanceContext(
        endpoint_id=ctx.endpoint_id,
        tool=ctx.tool,
        state="OBSERVING",
        state_since=now,
        observation_expires_at=now + timedelta(seconds=observation_window_seconds),
        cooldown_expires_at=ctx.cooldown_expires_at,
        trigger_budget_window_start=ctx.trigger_budget_window_start,
        alert_triggered_scans_in_window=ctx.alert_triggered_scans_in_window,
    )


def transition_to_elevated(
    ctx: VigilanceContext,
    now: datetime | None = None,
) -> VigilanceContext:
    """OBSERVING -> ELEVATED when corroborated or strong trigger."""
    now = now or datetime.now(timezone.utc)
    return VigilanceContext(
        endpoint_id=ctx.endpoint_id,
        tool=ctx.tool,
        state="ELEVATED",
        state_since=now,
        observation_expires_at=ctx.observation_expires_at,
        cooldown_expires_at=ctx.cooldown_expires_at,
        trigger_budget_window_start=ctx.trigger_budget_window_start,
        alert_triggered_scans_in_window=ctx.alert_triggered_scans_in_window,
    )


def transition_to_cooldown(
    ctx: VigilanceContext,
    cooldown_seconds: int,
    now: datetime | None = None,
) -> VigilanceContext:
    """ELEVATED -> COOLDOWN after full scan launched. Sets cooldown_expires_at."""
    now = now or datetime.now(timezone.utc)
    from datetime import timedelta
    return VigilanceContext(
        endpoint_id=ctx.endpoint_id,
        tool=ctx.tool,
        state="COOLDOWN",
        state_since=now,
        observation_expires_at=None,
        cooldown_expires_at=now + timedelta(seconds=cooldown_seconds),
        trigger_budget_window_start=ctx.trigger_budget_window_start,
        alert_triggered_scans_in_window=ctx.alert_triggered_scans_in_window + 1,
    )


def transition_to_idle_from_cooldown(
    ctx: VigilanceContext,
    now: datetime | None = None,
) -> VigilanceContext | None:
    """COOLDOWN -> IDLE when cooldown_expires_at has passed. Returns new context or None if not expired."""
    now = now or datetime.now(timezone.utc)
    if ctx.state != "COOLDOWN" or ctx.cooldown_expires_at is None:
        return None
    if now < ctx.cooldown_expires_at:
        return None
    return VigilanceContext(
        endpoint_id=ctx.endpoint_id,
        tool=ctx.tool,
        state="IDLE",
        state_since=now,
        observation_expires_at=None,
        cooldown_expires_at=None,
        trigger_budget_window_start=ctx.trigger_budget_window_start,
        alert_triggered_scans_in_window=ctx.alert_triggered_scans_in_window,
    )


def observation_expired(ctx: VigilanceContext, now: datetime | None = None) -> bool:
    """True if in OBSERVING and observation_expires_at has passed."""
    now = now or datetime.now(timezone.utc)
    if ctx.state != "OBSERVING" or ctx.observation_expires_at is None:
        return False
    return now >= ctx.observation_expires_at
