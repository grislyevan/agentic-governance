"""Endpoints router: manage monitored workstations."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.config import settings
from core.database import get_db
from core.tenant import get_tenant_id as _get_tenant_id, resolve_auth, require_role, get_tenant_filter
from models.endpoint import (
    ENDPOINT_STATUS_ACTIVE,
    Endpoint,
)
from schemas.endpoints import (
    EndpointCreate,
    EndpointListResponse,
    EndpointResponse,
    EndpointStatusResponse,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_endpoint(
    request: Request,
    body: EndpointCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointResponse:
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    existing = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id, Endpoint.hostname == body.hostname
    ).first()
    if existing:
        logger.warning("Duplicate endpoint registration: %s (tenant %s)", body.hostname, tenant_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Endpoint already registered")

    endpoint = Endpoint(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        hostname=body.hostname,
        os_info=body.os_info,
        posture=body.posture,
    )
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return EndpointResponse.model_validate(endpoint)


@router.get("", response_model=EndpointListResponse)
def list_endpoints(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    q = db.query(Endpoint).filter(get_tenant_filter(auth, Endpoint))
    total = q.with_entities(func.count()).scalar() or 0
    items = q.order_by(Endpoint.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return EndpointListResponse(
        total=total, page=page, page_size=page_size,
        items=[EndpointResponse.model_validate(e) for e in items],
    )


@router.get("/status", response_model=list[EndpointStatusResponse], tags=["heartbeat"])
def endpoint_status(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> list[EndpointStatusResponse]:
    """Return computed liveness status for visible endpoints."""
    auth = resolve_auth(authorization, x_api_key, db)
    endpoints = (
        db.query(Endpoint)
        .filter(get_tenant_filter(auth, Endpoint))
        .order_by(Endpoint.hostname)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    now = datetime.now(timezone.utc)
    results: list[EndpointStatusResponse] = []
    for ep in endpoints:
        computed = ep.compute_status()
        last = ep.last_seen_at
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds() if last else None
        results.append(EndpointStatusResponse(
            id=ep.id,
            hostname=ep.hostname,
            status=computed,
            last_seen_at=ep.last_seen_at,
            heartbeat_interval=ep.heartbeat_interval,
            seconds_since_heartbeat=round(elapsed, 1) if elapsed is not None else None,
        ))
    return results


class HeartbeatRequest(BaseModel):
    hostname: str = Field(max_length=255)
    interval_seconds: int = Field(default=settings.default_heartbeat_interval, ge=30, le=86400)


class HeartbeatResponse(BaseModel):
    status: str
    endpoint_id: str
    endpoint_status: str
    next_expected_in: int


@router.post("/heartbeat", response_model=HeartbeatResponse, tags=["heartbeat"])
@limiter.limit("60/minute")
def heartbeat(
    request: Request,
    body: HeartbeatRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> HeartbeatResponse:
    """Record that an endpoint agent is alive.

    Updates ``last_seen_at`` on the matching endpoint row.  If no row
    exists yet for this hostname the endpoint is auto-registered so that
    the first heartbeat from a new machine creates its record immediately.

    The response includes ``next_expected_in`` (seconds) so the server can
    flag endpoints as stale if they miss heartbeats.
    """
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    endpoint = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.hostname == body.hostname,
    ).first()

    now = datetime.now(timezone.utc)

    if endpoint is None:
        endpoint = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            hostname=body.hostname,
            posture="unmanaged",
            heartbeat_interval=body.interval_seconds,
            status=ENDPOINT_STATUS_ACTIVE,
            last_seen_at=now,
        )
        db.add(endpoint)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            endpoint = db.query(Endpoint).filter(
                Endpoint.tenant_id == tenant_id,
                Endpoint.hostname == body.hostname,
            ).first()
    else:
        endpoint.last_seen_at = now
        endpoint.heartbeat_interval = body.interval_seconds
        endpoint.status = ENDPOINT_STATUS_ACTIVE

    db.commit()
    db.refresh(endpoint)

    return HeartbeatResponse(
        status="ok",
        endpoint_id=endpoint.id,
        endpoint_status=endpoint.status,
        next_expected_in=body.interval_seconds,
    )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, get_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        logger.warning("Endpoint %s not found for user %s", endpoint_id, auth.user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return EndpointResponse.model_validate(endpoint)


# ---------------------------------------------------------------------------
# Cryptographic enrollment (Feature 4 — Signed Canonical Events)
# ---------------------------------------------------------------------------

class EnrollRequest(BaseModel):
    hostname: str = Field(max_length=255)
    public_key_pem: str = Field(max_length=2048)


class EnrollResponse(BaseModel):
    endpoint_id: str
    key_fingerprint: str
    enrolled_at: str


@router.post("/enroll", response_model=EnrollResponse, status_code=status.HTTP_201_CREATED, tags=["enrollment"])
@limiter.limit("10/minute")
def enroll_endpoint(
    request: Request,
    body: EnrollRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EnrollResponse:
    """Enroll an endpoint with its Ed25519 public key for event signing.

    The collector generates a keypair locally and sends the public key
    here.  The API stores the key so it can verify event signatures.
    Re-enrollment (key rotation) replaces the existing key.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    now = datetime.now(timezone.utc)

    fingerprint = hashlib.sha256(body.public_key_pem.encode()).hexdigest()

    endpoint = db.query(Endpoint).filter(
        Endpoint.tenant_id == auth.tenant_id,
        Endpoint.hostname == body.hostname,
    ).first()

    is_rotation = endpoint is not None
    if endpoint is None:
        endpoint = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=auth.tenant_id,
            hostname=body.hostname,
            posture="unmanaged",
            signing_public_key=body.public_key_pem,
            key_fingerprint=fingerprint,
            enrolled_at=now,
            last_seen_at=now,
            status=ENDPOINT_STATUS_ACTIVE,
        )
        db.add(endpoint)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            endpoint = db.query(Endpoint).filter(
                Endpoint.tenant_id == auth.tenant_id,
                Endpoint.hostname == body.hostname,
            ).first()
    else:
        endpoint.signing_public_key = body.public_key_pem
        endpoint.key_fingerprint = fingerprint
        endpoint.enrolled_at = now

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint.key_rotated" if is_rotation else "endpoint.enrolled",
        resource_type="endpoint",
        resource_id=endpoint.id,
        detail={"hostname": body.hostname, "key_fingerprint": fingerprint},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(endpoint)

    return EnrollResponse(
        endpoint_id=endpoint.id,
        key_fingerprint=fingerprint,
        enrolled_at=now.isoformat(),
    )
