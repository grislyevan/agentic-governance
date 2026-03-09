"""Events router: ingest and query canonical detection events."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.database import get_db
from core.tenant import get_tenant_id as _get_tenant_id
from models.endpoint import Endpoint
from models.event import Event
from schemas.events import EventIngest, EventListResponse, EventResponse

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

try:
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

router = APIRouter(prefix="/events", tags=["events"])


def _get_or_create_endpoint(
    tenant_id: str, endpoint_data: dict[str, Any] | None, db: Session
) -> str | None:
    if not endpoint_data:
        return None
    hostname = endpoint_data.get("id") or endpoint_data.get("hostname", "unknown")
    ep = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id, Endpoint.hostname == hostname
    ).first()
    if not ep:
        ep = Endpoint(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            hostname=hostname,
            os_info=endpoint_data.get("os"),
            posture=endpoint_data.get("posture", "unmanaged"),
        )
        db.add(ep)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            ep = db.query(Endpoint).filter(
                Endpoint.tenant_id == tenant_id, Endpoint.hostname == hostname
            ).first()
    ep.last_seen_at = datetime.now(timezone.utc)
    return ep.id


def _verify_signature(body: EventIngest, db: Session, tenant_id: str) -> bool | None:
    """Verify the Ed25519 signature on an incoming event.

    Returns True if valid, False if invalid, None if unsigned or
    crypto is unavailable.
    """
    sig_hex = body.signature
    fingerprint = body.key_fingerprint
    if not sig_hex or not fingerprint or not _HAS_CRYPTO:
        return None

    ep = db.query(Endpoint).filter(
        Endpoint.tenant_id == tenant_id,
        Endpoint.key_fingerprint == fingerprint,
    ).first()
    if ep is None or ep.signing_public_key is None:
        logger.warning("Signature from unknown fingerprint %s", fingerprint)
        return False

    try:
        pub_key = load_pem_public_key(ep.signing_public_key.encode())
        if not isinstance(pub_key, Ed25519PublicKey):
            return False

        event_dict = body.model_dump(exclude={"signature", "key_fingerprint"})
        filtered = {k: v for k, v in event_dict.items() if v is not None}
        canonical = json.dumps(filtered, sort_keys=True, separators=(",", ":"), default=str).encode()
        sig_bytes = bytes.fromhex(sig_hex)
        pub_key.verify(sig_bytes, canonical)
        return True
    except Exception:
        logger.warning("Signature verification failed for fingerprint %s", fingerprint)
        return False


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("120/minute")
def ingest_event(
    request: Request,
    body: EventIngest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EventResponse:
    """Ingest a single canonical event from the collector agent.

    If the event carries ``_signature`` and ``_key_fingerprint``, the
    server verifies the Ed25519 signature against the enrolled public
    key.  Events with invalid signatures are rejected with 403.
    """
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    existing = db.query(Event).filter(
        Event.event_id == body.event_id,
        Event.tenant_id == tenant_id,
    ).first()
    if existing:
        return EventResponse.model_validate(existing)

    sig_verified = _verify_signature(body, db, tenant_id)
    if sig_verified is False:
        logger.warning("Rejected event %s: signature verification failed", body.event_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Event signature verification failed",
        )

    endpoint_id = _get_or_create_endpoint(tenant_id, body.endpoint, db)

    tool = body.tool or {}
    policy = body.policy or {}
    severity = body.severity or {}

    attribution_sources = tool.get("attribution_sources")
    if isinstance(attribution_sources, list):
        attribution_sources = ",".join(attribution_sources)

    event = Event(
        id=str(uuid.uuid4()),
        event_id=body.event_id,
        tenant_id=tenant_id,
        endpoint_id=endpoint_id,
        event_type=body.event_type,
        event_version=body.event_version,
        observed_at=body.observed_at,
        session_id=body.session_id,
        trace_id=body.trace_id,
        parent_event_id=body.parent_event_id,
        tool_name=tool.get("name"),
        tool_class=tool.get("class"),
        tool_version=tool.get("version"),
        attribution_confidence=tool.get("attribution_confidence"),
        attribution_sources=attribution_sources,
        decision_state=policy.get("decision_state"),
        rule_id=policy.get("rule_id"),
        severity_level=severity.get("level"),
        signature_verified=sig_verified,
        payload=body.model_dump(mode="json"),
    )
    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(Event).filter(
            Event.event_id == body.event_id,
            Event.tenant_id == tenant_id,
        ).first()
        if existing:
            return EventResponse.model_validate(existing)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Duplicate event_id")
    db.refresh(event)
    return EventResponse.model_validate(event)


@router.get("", response_model=EventListResponse)
def list_events(
    event_type: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    tool_class: str | None = Query(default=None),
    decision_state: str | None = Query(default=None),
    endpoint_id: str | None = Query(default=None),
    observed_after: datetime | None = Query(default=None),
    observed_before: datetime | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EventListResponse:
    """List events for the authenticated tenant with optional filtering."""
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    q = db.query(Event).filter(Event.tenant_id == tenant_id)

    if event_type:
        q = q.filter(Event.event_type == event_type)
    if tool_name:
        q = q.filter(Event.tool_name == tool_name)
    if tool_class:
        q = q.filter(Event.tool_class == tool_class)
    if decision_state:
        q = q.filter(Event.decision_state == decision_state)
    if endpoint_id:
        q = q.filter(Event.endpoint_id == endpoint_id)
    if observed_after:
        q = q.filter(Event.observed_at >= observed_after)
    if observed_before:
        q = q.filter(Event.observed_at <= observed_before)
    if search:
        q = q.filter(Event.tool_name.ilike(f"%{search}%"))

    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(desc(Event.observed_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return EventListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EventResponse.model_validate(e) for e in items],
    )
