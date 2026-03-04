"""Endpoints router: manage monitored workstations."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.auth import is_valid_token
from ..core.database import get_db
from ..models.endpoint import (
    ENDPOINT_STATUS_ACTIVE,
    Endpoint,
)
from ..models.user import User
from ..schemas.endpoints import (
    EndpointCreate,
    EndpointListResponse,
    EndpointResponse,
    EndpointStatusResponse,
)

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


def _get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    if authorization and authorization.startswith("Bearer "):
        payload = is_valid_token(authorization.removeprefix("Bearer ").strip())
        if payload:
            return payload["tenant_id"]
    if x_api_key:
        user = db.query(User).filter(User.api_key == x_api_key, User.is_active.is_(True)).first()
        if user:
            return user.tenant_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


@router.post("", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
def create_endpoint(
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
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointListResponse:
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    items = db.query(Endpoint).filter(Endpoint.tenant_id == tenant_id).all()
    total = db.query(func.count()).select_from(Endpoint).filter(Endpoint.tenant_id == tenant_id).scalar() or 0
    return EndpointListResponse(total=total, items=[EndpointResponse.model_validate(e) for e in items])


@router.get("/status", response_model=list[EndpointStatusResponse], tags=["heartbeat"])
def endpoint_status(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> list[EndpointStatusResponse]:
    """Return computed liveness status for every endpoint in the tenant."""
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == tenant_id).all()

    now = datetime.now(timezone.utc)
    results: list[EndpointStatusResponse] = []
    for ep in endpoints:
        computed = ep.compute_status()
        elapsed = (now - ep.last_seen_at).total_seconds() if ep.last_seen_at else None
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
    hostname: str
    interval_seconds: int = 300


class HeartbeatResponse(BaseModel):
    status: str
    endpoint_id: str
    endpoint_status: str
    next_expected_in: int


@router.post("/heartbeat", response_model=HeartbeatResponse, tags=["heartbeat"])
def heartbeat(
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
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, Endpoint.tenant_id == tenant_id
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    return EndpointResponse.model_validate(endpoint)


# ---------------------------------------------------------------------------
# Cryptographic enrollment (Feature 4 — Signed Canonical Events)
# ---------------------------------------------------------------------------

class EnrollRequest(BaseModel):
    hostname: str
    public_key_pem: str


class EnrollResponse(BaseModel):
    endpoint_id: str
    key_fingerprint: str
    enrolled_at: str


@router.post("/enroll", response_model=EnrollResponse, status_code=status.HTTP_201_CREATED, tags=["enrollment"])
def enroll_endpoint(
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
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    now = datetime.now(timezone.utc)

    fingerprint = hashlib.sha256(body.public_key_pem.encode()).hexdigest()

    endpoint = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.hostname == body.hostname,
    ).first()

    if endpoint is None:
        endpoint = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            hostname=body.hostname,
            posture="unmanaged",
            signing_public_key=body.public_key_pem,
            key_fingerprint=fingerprint,
            enrolled_at=now,
            last_seen_at=now,
            status=ENDPOINT_STATUS_ACTIVE,
        )
        db.add(endpoint)
    else:
        endpoint.signing_public_key = body.public_key_pem
        endpoint.key_fingerprint = fingerprint
        endpoint.enrolled_at = now

    db.commit()
    db.refresh(endpoint)

    return EnrollResponse(
        endpoint_id=endpoint.id,
        key_fingerprint=fingerprint,
        enrolled_at=now.isoformat(),
    )
