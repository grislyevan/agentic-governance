"""Audit log router: read-only access to the tenant audit trail."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.audit import AuditLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit-log", tags=["audit"])


class AuditLogResponse(BaseModel):
    id: str
    actor_id: str | None
    actor_type: str
    action: str
    resource_type: str | None
    resource_id: str | None
    detail: dict
    ip_address: str | None
    occurred_at: str

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> AuditLogListResponse:
    """List audit log entries for the authenticated tenant."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")
    tenant_id = auth.tenant_id

    q = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)

    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)

    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(desc(AuditLog.occurred_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[AuditLogResponse.model_validate(e) for e in items],
    )
