"""Enforcement router: EDR provider config and service recovery.

EDR config routes let admins bind endpoints to enforcement providers
(CrowdStrike, SentinelOne). Disabled-services routes handle anti-resurrection
recovery -- restoring services that were disabled during escalation.

Posture management lives in routers/posture.py.
Allow-list governance lives in routers/allow_list.py.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.database import get_db, SessionLocal
from core.auth_cookies import get_authorization
from core.tenant import (
    resolve_auth,
    require_role,
    get_tenant_filter,
    strict_tenant_filter,
)
from integrations import enforcement_router as enf_router
from models.endpoint import Endpoint
from routers._enforcement_shared import VALID_PROVIDERS

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/enforcement", tags=["enforcement"])


# -- EDR enforcement config schemas -----------------------------------------


class EDRConfigUpdate(BaseModel):
    enforcement_provider: str | None = Field(
        default=None,
        max_length=64,
        description="Provider name (e.g. 'crowdstrike') or null to clear",
    )
    edr_host_id: str | None = Field(
        default=None,
        max_length=255,
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
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Configure EDR enforcement provider for an endpoint. Admin/owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ep = (
        db.query(Endpoint)
        .filter(
            Endpoint.id == endpoint_id,
            strict_tenant_filter(
                auth, Endpoint
            ),  # mutation path: strict tenant scope (BOLA fix)
        )
        .first()
    )
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
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Check whether the EDR provider can reach this endpoint."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    ep = (
        db.query(Endpoint)
        .filter(
            Endpoint.id == endpoint_id,
            strict_tenant_filter(auth, Endpoint),
        )
        .first()
    )
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    available = False
    if ep.enforcement_provider:
        provider = enf_router.get_provider(ep.enforcement_provider)
        if provider:
            try:
                available = await provider.available_for_endpoint(ep.hostname)
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                logger.warning(
                    "EDR availability check failed for %s: %s", ep.hostname, exc
                )
            except Exception:
                logger.exception(
                    "Unexpected error checking EDR availability for %s", ep.hostname
                )

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
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Dry-run EDR connectivity: resolve host, open+close RTR session."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ep = (
        db.query(Endpoint)
        .filter(
            Endpoint.id == endpoint_id,
            strict_tenant_filter(auth, Endpoint),
        )
        .first()
    )
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    if not ep.enforcement_provider:
        raise HTTPException(
            status_code=400,
            detail="No enforcement provider configured for this endpoint",
        )

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
                    session_id = await cs.initiate_rtr_session(
                        edr_host_id, client=client
                    )
                    if session_id:
                        rtr_session_ok = True
                        await cs.close_rtr_session(session_id, client=client)

                if edr_host_id != ep.edr_host_id:
                    ep.edr_host_id = edr_host_id
                    db.commit()
    except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
        logger.warning("EDR test network error for endpoint %s: %s", endpoint_id, exc)
    except Exception:
        logger.exception("EDR test failed for endpoint %s", endpoint_id)

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


# -- Disabled services (Task 11b: anti-resurrection recovery) ---------------


class DisabledServiceResponse(BaseModel):
    endpoint_id: str
    hostname: str
    disabled_services: list[dict]


class DisabledServicesListResponse(BaseModel):
    total: int
    items: list[DisabledServiceResponse]


class RestoreServicesRequest(BaseModel):
    endpoint_id: str = Field(
        ..., description="Endpoint whose services should be restored"
    )
    service_ids: list[str] = Field(
        default_factory=list,
        description="Specific service IDs to restore. Empty list restores all.",
    )


class RestoreServicesResponse(BaseModel):
    endpoint_id: str
    hostname: str
    queued: int
    service_ids: list[str]


@router.get("/disabled-services", response_model=DisabledServicesListResponse)
@limiter.limit("60/minute")
def list_disabled_services(
    request: Request,
    endpoint_id: str | None = Query(default=None),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """List all endpoints with services disabled by anti-resurrection escalation."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    q = db.query(Endpoint).filter(
        get_tenant_filter(auth, Endpoint),
        Endpoint.disabled_services.isnot(None),
    )
    if endpoint_id:
        q = q.filter(Endpoint.id == endpoint_id)

    endpoints = q.limit(10_000).all()

    items = []
    for ep in endpoints:
        services = ep.disabled_services or []
        if services:
            items.append(
                DisabledServiceResponse(
                    endpoint_id=ep.id,
                    hostname=ep.hostname,
                    disabled_services=services,
                )
            )

    return DisabledServicesListResponse(total=len(items), items=items)


@router.post("/restore-services", response_model=RestoreServicesResponse)
@limiter.limit("10/minute")
async def restore_services(
    request: Request,
    body: RestoreServicesRequest,
    background_tasks: BackgroundTasks,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Queue service restoration for an endpoint.

    For TCP-connected agents, pushes a restore command immediately.
    For HTTP-only agents, the restore command is delivered on the next heartbeat.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ep = (
        db.query(Endpoint)
        .filter(
            Endpoint.id == body.endpoint_id,
            strict_tenant_filter(
                auth, Endpoint
            ),  # mutation path: strict tenant scope (BOLA fix)
        )
        .first()
    )
    if not ep:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    current_disabled = ep.disabled_services or []
    if not current_disabled:
        raise HTTPException(
            status_code=400, detail="No disabled services on this endpoint"
        )

    if body.service_ids:
        known_ids = {
            s.get("service_id") for s in current_disabled if isinstance(s, dict)
        }
        unknown = [sid for sid in body.service_ids if sid not in known_ids]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown service IDs: {unknown}",
            )
        restore_ids = body.service_ids
    else:
        restore_ids = [
            s.get("service_id")
            for s in current_disabled
            if isinstance(s, dict) and s.get("service_id")
        ]

    existing_pending = ep.pending_restore_services or []
    merged = list(set(existing_pending + restore_ids))
    ep.pending_restore_services = merged

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.restore_services_queued",
        resource_type="endpoint",
        resource_id=ep.id,
        detail={
            "hostname": ep.hostname,
            "service_ids": restore_ids,
        },
    )

    db.commit()

    background_tasks.add_task(
        _push_restore_to_agent,
        request,
        ep.id,
        restore_ids,
    )

    return RestoreServicesResponse(
        endpoint_id=ep.id,
        hostname=ep.hostname,
        queued=len(restore_ids),
        service_ids=restore_ids,
    )


async def _push_restore_to_agent(
    request: Request,
    endpoint_id: str,
    service_ids: list[str],
) -> None:
    """Best-effort push of restore command to a TCP-connected agent."""
    gateway = getattr(request.app.state, "gateway", None)
    if not gateway:
        return
    try:
        from protocol.messages import command_msg

        msg = command_msg(
            command="restore_services",
            command_id=str(uuid.uuid4()),
            params={"service_ids": service_ids},
        )
        sent = await gateway.push_to_endpoint(endpoint_id, msg)
        if sent:
            logger.info(
                "Pushed restore_services command to endpoint %s via TCP", endpoint_id
            )
            db = SessionLocal()
            try:
                ep = db.query(Endpoint).filter(Endpoint.id == endpoint_id).first()
                if ep:
                    ep.pending_restore_services = None
                    db.commit()
            finally:
                db.close()
    except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
        logger.warning(
            "Could not push restore command to %s (not connected via TCP): %s",
            endpoint_id,
            exc,
        )
    except Exception:
        logger.exception("Unexpected error pushing restore command to %s", endpoint_id)
