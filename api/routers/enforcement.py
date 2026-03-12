"""Enforcement router: manage endpoint posture, allow-lists, and EDR enforcement config.

Posture controls whether agents enforce block decisions locally.
Allow-list entries exempt specific tools from enforcement.
EDR config routes let admins bind endpoints to enforcement providers.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.config import settings
from core.database import get_db, SessionLocal
from core.tenant import resolve_auth, require_role, get_tenant_filter
from integrations import enforcement_router as enf_router
from models.allow_list import AllowListEntry
from models.endpoint import Endpoint

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/enforcement", tags=["enforcement"])

VALID_POSTURES = {"passive", "audit", "active"}
VALID_PROVIDERS = {"crowdstrike", "sentinelone"}


async def _push_posture_to_agent(
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
    except Exception:
        logger.debug("Could not push posture to %s (not connected via TCP)", endpoint_id)


async def _push_tenant_posture_to_tcp(
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
            e.pattern for e in db.query(AllowListEntry).filter(AllowListEntry.tenant_id == tenant_id).all()
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
            except Exception:
                logger.debug("Could not push posture to %s", ep.id)
    finally:
        db.close()


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


class AllowListEntryResponse(BaseModel):
    id: str
    pattern: str
    pattern_type: str
    description: str | None
    created_by: str | None
    created_at: str

    model_config = {"from_attributes": True}


class AllowListEntryCreate(BaseModel):
    pattern: str = Field(..., min_length=3, max_length=512)
    pattern_type: str = Field(default="name", pattern="^(name|path|hash)$")
    description: str | None = Field(default=None, max_length=512)


class AllowListResponse(BaseModel):
    total: int
    items: list[AllowListEntryResponse]


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
    authorization: str | None = Header(default=None),
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
        get_tenant_filter(auth, Endpoint),
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

    allow_list = [
        e.pattern for e in db.query(AllowListEntry).filter(AllowListEntry.tenant_id == auth.tenant_id).all()
    ]
    background_tasks.add_task(
        _push_posture_to_agent,
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
    authorization: str | None = Header(default=None),
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
        _push_tenant_posture_to_tcp,
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
    authorization: str | None = Header(default=None),
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


# -- Allow-list endpoints --------------------------------------------------

@router.get("/allow-list", response_model=AllowListResponse)
@limiter.limit("60/minute")
def list_allow_list(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """List all allow-list entries for the tenant."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    tenant_id = auth.tenant_id
    entries = (
        db.query(AllowListEntry)
        .filter(AllowListEntry.tenant_id == tenant_id)
        .order_by(AllowListEntry.created_at.desc())
        .all()
    )

    return AllowListResponse(
        total=len(entries),
        items=[
            AllowListEntryResponse(
                id=e.id,
                pattern=e.pattern,
                pattern_type=e.pattern_type,
                description=e.description,
                created_by=e.created_by,
                created_at=e.created_at.isoformat() if e.created_at else "",
            )
            for e in entries
        ],
    )


@router.post(
    "/allow-list",
    response_model=AllowListEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
def create_allow_list_entry(
    request: Request,
    body: AllowListEntryCreate,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Add a new allow-list entry. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant_id = auth.tenant_id
    entry = AllowListEntry(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        pattern=body.pattern,
        pattern_type=body.pattern_type,
        description=body.description,
        created_by=auth.user_id,
    )
    db.add(entry)

    audit_record(
        db,
        tenant_id=tenant_id,
        actor_id=auth.user_id,
        action="enforcement.allow_list_added",
        resource_type="allow_list_entry",
        resource_id=entry.id,
        detail={
            "pattern": body.pattern,
            "pattern_type": body.pattern_type,
        },
    )

    db.commit()
    db.refresh(entry)

    allow_list = [
        e.pattern for e in db.query(AllowListEntry).filter(AllowListEntry.tenant_id == tenant_id).all()
    ]
    endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == tenant_id).all()
    for ep in endpoints:
        background_tasks.add_task(
            _push_posture_to_agent,
            request,
            ep.id,
            ep.enforcement_posture,
            ep.auto_enforce_threshold,
            allow_list,
        )

    return AllowListEntryResponse(
        id=entry.id,
        pattern=entry.pattern,
        pattern_type=entry.pattern_type,
        description=entry.description,
        created_by=entry.created_by,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
    )


@router.delete(
    "/allow-list/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
@limiter.limit("30/minute")
def delete_allow_list_entry(
    request: Request,
    entry_id: str,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Remove an allow-list entry. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    entry = db.query(AllowListEntry).filter(
        AllowListEntry.id == entry_id,
        AllowListEntry.tenant_id == auth.tenant_id,
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Allow-list entry not found")

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.allow_list_removed",
        resource_type="allow_list_entry",
        resource_id=entry_id,
        detail={"pattern": entry.pattern, "pattern_type": entry.pattern_type},
    )

    db.delete(entry)
    db.commit()

    allow_list = [
        e.pattern for e in db.query(AllowListEntry).filter(AllowListEntry.tenant_id == auth.tenant_id).all()
    ]
    endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == auth.tenant_id).all()
    for ep in endpoints:
        background_tasks.add_task(
            _push_posture_to_agent,
            request,
            ep.id,
            ep.enforcement_posture,
            ep.auto_enforce_threshold,
            allow_list,
        )


# -- EDR enforcement config schemas -----------------------------------------

class EDRConfigUpdate(BaseModel):
    enforcement_provider: str | None = Field(
        default=None, max_length=64,
        description="Provider name (e.g. 'crowdstrike') or null to clear",
    )
    edr_host_id: str | None = Field(
        default=None, max_length=255,
        description="Cached EDR host ID (optional; resolved automatically if omitted)",
    )


class EDRConfigResponse(BaseModel):
    endpoint_id: str
    hostname: str
    enforcement_provider: str | None
    edr_host_id: str | None

    model_config = {"from_attributes": True}


class EDRStatusResponse(BaseModel):
    endpoint_id: str
    hostname: str
    enforcement_provider: str | None
    edr_host_id: str | None
    available: bool
    registered_providers: list[str]


class EDRTestResponse(BaseModel):
    endpoint_id: str
    hostname: str
    provider: str
    host_resolved: bool
    edr_host_id: str | None
    rtr_session_ok: bool


# -- EDR enforcement config routes ------------------------------------------

@router.put(
    "/endpoints/{endpoint_id}/edr-config",
    response_model=EDRConfigResponse,
)
@limiter.limit("30/minute")
def set_endpoint_edr_config(
    request: Request,
    endpoint_id: str,
    body: EDRConfigUpdate,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Configure EDR enforcement provider for an endpoint. Admin/owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ep = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id,
        get_tenant_filter(auth, Endpoint),
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if body.enforcement_provider and body.enforcement_provider not in VALID_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{body.enforcement_provider}'. Valid: {sorted(VALID_PROVIDERS)}",
        )

    old_provider = ep.enforcement_provider
    ep.enforcement_provider = body.enforcement_provider
    if body.edr_host_id is not None:
        ep.edr_host_id = body.edr_host_id

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.edr_config_changed",
        resource_type="endpoint",
        resource_id=endpoint_id,
        detail={
            "old_provider": old_provider,
            "new_provider": body.enforcement_provider,
            "edr_host_id": ep.edr_host_id,
            "hostname": ep.hostname,
        },
    )

    db.commit()
    db.refresh(ep)

    return EDRConfigResponse(
        endpoint_id=ep.id,
        hostname=ep.hostname,
        enforcement_provider=ep.enforcement_provider,
        edr_host_id=ep.edr_host_id,
    )


@router.get(
    "/endpoints/{endpoint_id}/edr-status",
    response_model=EDRStatusResponse,
)
@limiter.limit("30/minute")
async def get_endpoint_edr_status(
    request: Request,
    endpoint_id: str,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Check whether the EDR provider can reach this endpoint."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    ep = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id,
        get_tenant_filter(auth, Endpoint),
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    available = False
    if ep.enforcement_provider:
        provider = enf_router.get_provider(ep.enforcement_provider)
        if provider:
            try:
                available = await provider.available_for_endpoint(ep.hostname)
            except Exception:
                logger.debug("EDR availability check failed for %s", ep.hostname)

    return EDRStatusResponse(
        endpoint_id=ep.id,
        hostname=ep.hostname,
        enforcement_provider=ep.enforcement_provider,
        edr_host_id=ep.edr_host_id,
        available=available,
        registered_providers=enf_router.registered_providers(),
    )


@router.post(
    "/edr-test/{endpoint_id}",
    response_model=EDRTestResponse,
)
@limiter.limit("10/minute")
async def test_edr_connectivity(
    request: Request,
    endpoint_id: str,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Dry-run EDR connectivity: resolve host, open+close RTR session."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ep = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id,
        get_tenant_filter(auth, Endpoint),
    ).first()
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if not ep.enforcement_provider:
        raise HTTPException(status_code=400, detail="No enforcement provider configured for this endpoint")

    provider = enf_router.get_provider(ep.enforcement_provider)
    if not provider:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{ep.enforcement_provider}' is not registered on this server",
        )

    host_resolved = False
    edr_host_id = ep.edr_host_id
    rtr_session_ok = False

    try:
        available = await provider.available_for_endpoint(ep.hostname)
        host_resolved = available

        if host_resolved and hasattr(provider, "_cs"):
            cs = provider._cs
            if not edr_host_id:
                edr_host_id = await cs.resolve_endpoint_id(ep.hostname)

            if edr_host_id:
                import httpx
                async with httpx.AsyncClient() as client:
                    session_id = await cs.initiate_rtr_session(edr_host_id, client=client)
                    if session_id:
                        rtr_session_ok = True
                        await cs.close_rtr_session(session_id, client=client)

                if edr_host_id != ep.edr_host_id:
                    ep.edr_host_id = edr_host_id
                    db.commit()
    except Exception:
        logger.warning("EDR test failed for endpoint %s", endpoint_id, exc_info=True)

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.edr_test",
        resource_type="endpoint",
        resource_id=endpoint_id,
        detail={
            "provider": ep.enforcement_provider,
            "host_resolved": host_resolved,
            "rtr_session_ok": rtr_session_ok,
        },
    )

    return EDRTestResponse(
        endpoint_id=ep.id,
        hostname=ep.hostname,
        provider=ep.enforcement_provider,
        host_resolved=host_resolved,
        edr_host_id=edr_host_id,
        rtr_session_ok=rtr_session_ok,
    )
