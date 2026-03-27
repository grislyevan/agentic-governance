"""Posture router: manage endpoint and tenant enforcement posture.

Posture controls whether agents enforce block decisions locally.
Three modes: passive (log only), audit (warn), active (block).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.config import settings
from core.database import get_db
from core.auth_cookies import get_authorization
from core.tenant import resolve_auth, require_role, strict_tenant_filter
from models.endpoint import Endpoint
from routers._enforcement_shared import (
    push_posture_to_agent,
    push_tenant_posture_to_tcp,
    get_active_allow_list_patterns,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/enforcement", tags=["enforcement"])


# -- Schemas ----------------------------------------------------------------

class PostureUpdate(BaseModel):
    enforcement_posture: str = Field(
        ..., pattern="^(passive|audit|active)$",
        description="One of: passive, audit, active",
    )
    auto_enforce_threshold: float | None = Field(
        default=None, ge=0.0, le=1.0,
        description="Minimum confidence for auto-enforcement (0.0 - 1.0)",
    )


class PostureResponse(BaseModel):
    endpoint_id: str
    hostname: str
    enforcement_posture: str
    auto_enforce_threshold: float

    model_config = {"from_attributes": True}


class TenantPostureUpdate(BaseModel):
    enforcement_posture: str = Field(
        ..., pattern="^(passive|audit|active)$",
    )
    auto_enforce_threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class TenantPostureResponse(BaseModel):
    updated: int
    enforcement_posture: str
    auto_enforce_threshold: float


class PostureSummaryResponse(BaseModel):
    total: int
    passive: int
    audit: int
    active: int


# -- Posture endpoints ------------------------------------------------------

@router.put(
    "/endpoints/{endpoint_id}/posture",
    response_model=PostureResponse,
)
@limiter.limit("30/minute")
async def set_endpoint_posture(
    request: Request,
    endpoint_id: str,
    body: PostureUpdate,
    background_tasks: BackgroundTasks,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Set enforcement posture for a single endpoint. Requires admin or owner role.
    Active posture requires owner role only."""
    auth = resolve_auth(authorization, x_api_key, db)
    if body.enforcement_posture == "active":
        require_role(auth, "owner")
    else:
        require_role(auth, "owner", "admin")

    ep = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id,
        strict_tenant_filter(auth, Endpoint),  # mutation path: strict tenant scope (BOLA fix)
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    old_posture = ep.enforcement_posture
    ep.enforcement_posture = body.enforcement_posture
    if body.auto_enforce_threshold is not None:
        ep.auto_enforce_threshold = body.auto_enforce_threshold

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.posture_changed",
        resource_type="endpoint",
        resource_id=endpoint_id,
        detail={
            "old_posture": old_posture,
            "new_posture": body.enforcement_posture,
            "auto_enforce_threshold": ep.auto_enforce_threshold,
            "hostname": ep.hostname,
        },
    )

    db.commit()
    db.refresh(ep)

    allow_list = get_active_allow_list_patterns(db, auth.tenant_id)
    background_tasks.add_task(
        push_posture_to_agent,
        request,
        endpoint_id,
        ep.enforcement_posture,
        ep.auto_enforce_threshold,
        allow_list,
    )

    return PostureResponse(
        endpoint_id=ep.id,
        hostname=ep.hostname,
        enforcement_posture=ep.enforcement_posture,
        auto_enforce_threshold=ep.auto_enforce_threshold,
    )


@router.put("/tenant-posture", response_model=TenantPostureResponse)
@limiter.limit("10/minute")
def set_tenant_posture(
    request: Request,
    body: TenantPostureUpdate,
    background_tasks: BackgroundTasks,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Set default enforcement posture for all endpoints in the tenant. Owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")

    tenant_id = auth.tenant_id
    threshold = body.auto_enforce_threshold or settings.default_auto_enforce_threshold

    updated = (
        db.query(Endpoint)
        .filter(Endpoint.tenant_id == tenant_id)
        .update({
            Endpoint.enforcement_posture: body.enforcement_posture,
            Endpoint.auto_enforce_threshold: threshold,
        })
    )

    audit_record(
        db,
        tenant_id=tenant_id,
        actor_id=auth.user_id,
        action="enforcement.tenant_posture_changed",
        resource_type="tenant",
        resource_id=tenant_id,
        detail={
            "new_posture": body.enforcement_posture,
            "auto_enforce_threshold": threshold,
            "endpoints_updated": updated,
        },
    )

    db.commit()

    background_tasks.add_task(
        push_tenant_posture_to_tcp,
        request,
        tenant_id,
        body.enforcement_posture,
        threshold,
    )

    return TenantPostureResponse(
        updated=updated,
        enforcement_posture=body.enforcement_posture,
        auto_enforce_threshold=threshold,
    )


@router.get("/posture-summary", response_model=PostureSummaryResponse)
@limiter.limit("60/minute")
def posture_summary(
    request: Request,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Return posture distribution across all endpoints in the tenant."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    tenant_id = auth.tenant_id
    rows = (
        db.query(Endpoint.enforcement_posture, func.count(Endpoint.id))
        .filter(Endpoint.tenant_id == tenant_id)
        .group_by(Endpoint.enforcement_posture)
        .all()
    )

    counts = {r[0]: r[1] for r in rows}
    total = sum(counts.values())

    return PostureSummaryResponse(
        total=total,
        passive=counts.get("passive", 0),
        audit=counts.get("audit", 0),
        active=counts.get("active", 0),
    )
