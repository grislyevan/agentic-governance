"""Endpoints router: manage monitored workstations."""

from __future__ import annotations

import hashlib
import logging
import secrets
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
from core.auth_cookies import get_authorization
from core.tenant import get_tenant_id as _get_tenant_id, resolve_auth, require_role, get_tenant_filter, strict_tenant_filter
from models.allow_list import AllowListEntry
from models.endpoint import (
    ENDPOINT_STATUS_ACTIVE,
    Endpoint,
)
from models.endpoint_profile import EndpointProfile
from models.policy import Policy
from schemas.endpoints import (
    DecommissionResponse,
    EndpointCreate,
    EndpointListResponse,
    EndpointResponse,
    EndpointStatusResponse,
    EndpointUpdate,
    UninstallTokenResponse,
    ValidateUninstallTokenRequest,
    ValidateUninstallTokenResponse,
)
from schemas.session_report import SessionReportListResponse

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/endpoints", tags=["endpoints"])


@router.post("", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_endpoint(
    request: Request,
    body: EndpointCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
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
        management_state=body.management_state,
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
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EndpointListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    q = db.query(Endpoint).filter(get_tenant_filter(auth, Endpoint))
    total = q.with_entities(func.count()).scalar() or 0
    items = q.order_by(Endpoint.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    response_items = []
    for e in items:
        resp = EndpointResponse.model_validate(e)
        resp.computed_status = e.compute_status()
        response_items.append(resp)
    return EndpointListResponse(
        total=total, page=page, page_size=page_size,
        items=response_items,
    )


@router.get("/status", response_model=list[EndpointStatusResponse], tags=["heartbeat"])
def endpoint_status(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
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
            is_stale=ep.is_stale,
        ))
    return results


class HeartbeatRequest(BaseModel):
    hostname: str = Field(max_length=255)
    interval_seconds: int = Field(default=settings.default_heartbeat_interval, ge=30, le=86400)
    telemetry_provider: str | None = Field(default=None, max_length=32)
    disabled_services: list[dict] | None = Field(
        default=None,
        description="Services disabled by anti-resurrection escalation, reported by agent",
    )


class HeartbeatResponse(BaseModel):
    status: str
    endpoint_id: str
    endpoint_status: str
    next_expected_in: int
    interval_seconds: int | None = Field(
        default=None,
        description="Server-desired heartbeat/scan interval; agent should apply and persist if present",
    )
    enforcement_posture: str = "passive"
    auto_enforce_threshold: float = 0.75
    allow_list: list[str] = Field(default_factory=list)
    allow_list_updated_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of the most recent allow-list change for this tenant",
    )
    restore_services: list[str] = Field(
        default_factory=list,
        description="Service IDs that the agent should re-enable",
    )
    behavioral_config: dict | None = Field(
        default=None,
        description="Per-profile behavioral threshold overrides; agent merges on top of file defaults",
    )
    policy_rules: list[dict] | None = Field(
        default=None,
        description="Per-tenant policy rules; when present, agent replaces its baseline rules with these",
    )


@router.post("/heartbeat", response_model=HeartbeatResponse, tags=["heartbeat"])
@limiter.limit("60/minute")
def heartbeat(
    request: Request,
    body: HeartbeatRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
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
            management_state="unmanaged",
            heartbeat_interval=body.interval_seconds,
            telemetry_provider=body.telemetry_provider,
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
        if body.telemetry_provider:
            endpoint.telemetry_provider = body.telemetry_provider

    if body.disabled_services is not None:
        endpoint.disabled_services = body.disabled_services

    db.commit()
    db.refresh(endpoint)

    entries = db.query(AllowListEntry).filter(AllowListEntry.tenant_id == endpoint.tenant_id).all()
    allow_list = [e.pattern for e in entries]
    latest_ts = max((e.created_at for e in entries), default=None) if entries else None
    allow_list_updated_at = latest_ts.isoformat() if latest_ts else None

    restore_services: list[str] = []
    if endpoint.pending_restore_services:
        restore_services = list(endpoint.pending_restore_services)
        endpoint.pending_restore_services = None
        db.commit()

    interval_seconds: int | None = None
    behavioral_config: dict | None = None
    if endpoint.endpoint_profile is not None:
        interval_seconds = endpoint.endpoint_profile.scan_interval_seconds
        behavioral_config = endpoint.endpoint_profile.behavioral_config

    # Include custom policy rules for this tenant if any exist.
    # Only non-baseline (custom) policies or tenants with modified baselines
    # trigger inclusion.  When all policies are default baselines, policy_rules
    # is omitted so the agent uses its local file.
    policy_rules: list[dict] | None = None
    try:
        custom_policies = (
            db.query(Policy)
            .filter(
                Policy.tenant_id == tenant_id,
                Policy.is_baseline.is_(False),
            )
            .all()
        )
        if custom_policies:
            # Tenant has custom rules: serialize ALL active policies for this tenant
            all_policies = (
                db.query(Policy)
                .filter(
                    Policy.tenant_id == tenant_id,
                    Policy.is_active.is_(True),
                )
                .all()
            )
            policy_rules = [
                {
                    "rule_id": p.rule_id,
                    "rule_version": p.rule_version,
                    "category": p.category,
                    "is_active": p.is_active,
                    "decision_state": p.parameters.get("decision_state", "detect"),
                    "conditions": p.parameters.get("conditions", {}),
                    "reason_codes": p.parameters.get("reason_codes", []),
                    "precedence": p.parameters.get("precedence", 999),
                    "is_fallback": p.parameters.get("is_fallback", False),
                    "is_overlay": p.parameters.get("overlay", False),
                }
                for p in all_policies
            ]
    except Exception:
        logger.debug("Could not query tenant policy rules", exc_info=True)

    return HeartbeatResponse(
        status="ok",
        endpoint_id=endpoint.id,
        endpoint_status=endpoint.status,
        next_expected_in=body.interval_seconds,
        interval_seconds=interval_seconds,
        enforcement_posture=endpoint.enforcement_posture,
        auto_enforce_threshold=endpoint.auto_enforce_threshold,
        allow_list=allow_list,
        allow_list_updated_at=allow_list_updated_at,
        restore_services=restore_services,
        behavioral_config=behavioral_config,
        policy_rules=policy_rules,
    )


@router.get("/{endpoint_id}/session-reports", response_model=SessionReportListResponse, tags=["session-reports"])
def get_endpoint_session_reports(
    endpoint_id: str,
    since: datetime | None = Query(default=None),
    before: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> SessionReportListResponse:
    """Return session reports for a single endpoint."""
    from core.session_aggregation import (
        DEFAULT_SESSION_GAP_MINUTES,
        aggregate_events_into_sessions,
        fetch_events_for_sessions,
    )
    from models.event import Event

    auth = resolve_auth(authorization, x_api_key, db)
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, strict_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    tenant_filter = get_tenant_filter(auth, Event)
    events = fetch_events_for_sessions(
        db, tenant_filter, endpoint_id=endpoint_id, observed_after=since, observed_before=before, limit=limit
    )
    reports = aggregate_events_into_sessions(
        events,
        session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES,
        endpoint_id=endpoint_id,
    )
    return SessionReportListResponse(items=reports)


@router.get("/{endpoint_id}", response_model=EndpointResponse)
def get_endpoint(
    endpoint_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
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


@router.patch("/{endpoint_id}", response_model=EndpointResponse)
def update_endpoint(
    endpoint_id: str,
    body: EndpointUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EndpointResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    # Use strict_tenant_filter on mutation: prevents cross-tenant write (BOLA fix)
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, strict_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")
    if body.endpoint_profile_id is not None:
        if body.endpoint_profile_id == "":
            endpoint.endpoint_profile_id = None
            if endpoint.management_state == "managed":
                endpoint.management_state = "unmanaged"
        else:
            profile = db.query(EndpointProfile).filter(
                EndpointProfile.id == body.endpoint_profile_id,
                EndpointProfile.tenant_id == auth.tenant_id,
            ).first()
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Profile not found or not in this tenant",
                )
            endpoint.endpoint_profile_id = body.endpoint_profile_id
            # Auto-promote to managed when a profile is assigned
            if endpoint.management_state != "managed":
                endpoint.management_state = "managed"
    if body.management_state is not None:
        endpoint.management_state = body.management_state
    db.commit()
    db.refresh(endpoint)
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
    authorization: str | None = Depends(get_authorization),
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
            management_state="unmanaged",
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


# ---------------------------------------------------------------------------
# Tamper control — uninstall token and decommission (Task 2)
# ---------------------------------------------------------------------------

@router.post("/{endpoint_id}/uninstall-token", response_model=UninstallTokenResponse)
def generate_uninstall_token(
    request: Request,
    endpoint_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> UninstallTokenResponse:
    """Generate a one-time uninstall authorization token for an endpoint.

    The plaintext token is returned once and never stored.  Only the
    SHA-256 hash is persisted so it can be verified later.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, strict_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    token = secrets.token_hex(32)
    endpoint.uninstall_token_hash = hashlib.sha256(token.encode()).hexdigest()
    db.commit()

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint.uninstall_token_generated",
        resource_type="endpoint",
        resource_id=endpoint.id,
        detail={"hostname": endpoint.hostname},
        ip_address=request.client.host if request.client else None,
    )

    return UninstallTokenResponse(uninstall_token=token)


@router.post("/{endpoint_id}/validate-uninstall-token", response_model=ValidateUninstallTokenResponse)
def validate_uninstall_token(
    endpoint_id: str,
    body: ValidateUninstallTokenRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> ValidateUninstallTokenResponse:
    """Validate an uninstall token against the stored hash."""
    auth = resolve_auth(authorization, x_api_key, db)
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, strict_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    if not endpoint.uninstall_token_hash:
        return ValidateUninstallTokenResponse(valid=False)

    candidate_hash = hashlib.sha256(body.token.encode()).hexdigest()
    valid = secrets.compare_digest(candidate_hash, endpoint.uninstall_token_hash)
    return ValidateUninstallTokenResponse(valid=valid)


@router.post("/{endpoint_id}/decommission", response_model=DecommissionResponse)
def decommission_endpoint(
    request: Request,
    endpoint_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> DecommissionResponse:
    """Mark an endpoint as decommissioned and remove it from governance."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    endpoint = db.query(Endpoint).filter(
        Endpoint.id == endpoint_id, strict_tenant_filter(auth, Endpoint)
    ).first()
    if not endpoint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint not found")

    endpoint.status = "decommissioned"
    endpoint.management_state = "unmanaged"
    db.commit()

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint.decommissioned",
        resource_type="endpoint",
        resource_id=endpoint.id,
        detail={"hostname": endpoint.hostname},
        ip_address=request.client.host if request.client else None,
    )

    return DecommissionResponse(
        id=endpoint.id,
        hostname=endpoint.hostname,
        status=endpoint.status,
    )
