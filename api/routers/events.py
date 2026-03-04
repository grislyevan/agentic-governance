"""Events router: ingest and query canonical detection events."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..core.auth import is_valid_token
from ..core.database import get_db
from ..models.endpoint import Endpoint
from ..models.event import Event
from ..models.user import User
from ..schemas.events import EventIngest, EventListResponse, EventResponse

router = APIRouter(prefix="/events", tags=["events"])


def _get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    """Resolve tenant_id from JWT or API key. Raises 401 on failure."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = is_valid_token(token)
        if payload:
            return payload["tenant_id"]

    if x_api_key:
        user = db.query(User).filter(User.api_key == x_api_key, User.is_active.is_(True)).first()
        if user:
            return user.tenant_id

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


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
    ep.last_seen_at = datetime.now(timezone.utc)
    return ep.id


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def ingest_event(
    body: EventIngest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EventResponse:
    """Ingest a single canonical event from the collector agent."""
    tenant_id = _get_tenant_id(authorization, x_api_key, db)

    existing = db.query(Event).filter(Event.event_id == body.event_id).first()
    if existing:
        return EventResponse.model_validate(existing)

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
        payload=body.model_dump(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return EventResponse.model_validate(event)


@router.get("", response_model=EventListResponse)
def list_events(
    event_type: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    tool_class: str | None = Query(default=None),
    decision_state: str | None = Query(default=None),
    endpoint_id: str | None = Query(default=None),
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
