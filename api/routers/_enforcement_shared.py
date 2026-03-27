"""Shared helpers for enforcement sub-routers (posture, allow-list, EDR).

These utilities are used by multiple enforcement modules and are kept here
to avoid circular imports while keeping the public router surface clean.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import Request

from core.database import SessionLocal
from models.allow_list import AllowListEntry
from models.endpoint import Endpoint

logger = logging.getLogger(__name__)

VALID_POSTURES = {"passive", "audit", "active"}
VALID_PROVIDERS = {"crowdstrike", "sentinelone"}


async def push_posture_to_agent(
    request: Request,
    endpoint_id: str,
    posture: str,
    threshold: float,
    allow_list: list[str] | None = None,
) -> None:
    """Best-effort push of posture to a TCP-connected agent."""
    gateway = getattr(request.app.state, "gateway", None)
    if not gateway:
        return
    try:
        sent = await gateway.push_posture(
            endpoint_id=endpoint_id,
            posture=posture,
            auto_enforce_threshold=threshold,
            allow_list=allow_list,
        )
        if sent:
            logger.info("Pushed posture %s to endpoint %s via TCP", posture, endpoint_id)
    except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
        logger.warning("Could not push posture to %s (not connected via TCP): %s", endpoint_id, exc)


async def push_tenant_posture_to_tcp(
    request: Request,
    tenant_id: str,
    posture: str,
    threshold: float,
) -> None:
    """Push posture to all TCP-connected agents for the tenant."""
    gateway = getattr(request.app.state, "gateway", None)
    if not gateway:
        return
    db = SessionLocal()
    try:
        allow_list = [
            e.pattern for e in db.query(AllowListEntry).filter(
                AllowListEntry.tenant_id == tenant_id,
                (AllowListEntry.expires_at == None) | (AllowListEntry.expires_at > datetime.now(timezone.utc)),  # noqa: E711
            ).all()
        ]
        endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == tenant_id).all()
        for ep in endpoints:
            try:
                sent = await gateway.push_posture(
                    endpoint_id=ep.id,
                    posture=posture,
                    auto_enforce_threshold=threshold,
                    allow_list=allow_list,
                )
                if sent:
                    logger.info("Pushed posture %s to endpoint %s via TCP", posture, ep.id)
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                logger.warning("Could not push posture to %s: %s", ep.id, exc)
    finally:
        db.close()


def get_active_allow_list_patterns(db, tenant_id: str) -> list[str]:
    """Return active (non-expired) allow-list patterns for a tenant."""
    return [
        e.pattern for e in db.query(AllowListEntry).filter(
            AllowListEntry.tenant_id == tenant_id,
            (AllowListEntry.expires_at == None) | (AllowListEntry.expires_at > datetime.now(timezone.utc)),  # noqa: E711
        ).all()
    ]


def serialize_allow_list_entry(e: AllowListEntry) -> dict:
    """Return a dict representation of an allow-list entry (includes tenant_id)."""
    return {
        "id": e.id,
        "tenant_id": e.tenant_id,
        "pattern": e.pattern,
        "pattern_type": e.pattern_type,
        "description": e.description,
        "created_by": e.created_by,
        "created_at": e.created_at.isoformat() if e.created_at else "",
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
        "scope": e.scope,
        "reason_code": e.reason_code,
        "owner_id": e.owner_id,
    }
