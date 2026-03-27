"""Allow-list router: CRUD and governance for enforcement exemptions.

Allow-list entries exempt specific tools from enforcement. Entries can be
scoped to tenant, endpoint, or tool level and support optional expiry.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.database import get_db
from core.auth_cookies import get_authorization
from core.tenant import resolve_auth, require_role, strict_tenant_filter
from models.allow_list import AllowListEntry
from models.endpoint import Endpoint
from routers._enforcement_shared import (
    push_posture_to_agent,
    get_active_allow_list_patterns,
    serialize_allow_list_entry,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/enforcement", tags=["enforcement"])


# -- Schemas ----------------------------------------------------------------

class AllowListEntryResponse(BaseModel):
    id: str
    tenant_id: str | None = None
    pattern: str
    pattern_type: str
    description: str | None
    created_by: str | None
    created_at: str
    expires_at: str | None
    scope: str | None
    reason_code: str | None
    owner_id: str | None

    model_config = {"from_attributes": True}


class AllowListEntryCreate(BaseModel):
    pattern: str = Field(..., min_length=3, max_length=512)
    pattern_type: str = Field(default="name", pattern="^(name|path|hash|process_name)$")
    description: str | None = Field(default=None, max_length=512)
    expires_at: datetime | None = None
    scope: str = Field(default="tenant", pattern="^(tenant|endpoint|tool)$")
    reason_code: str | None = Field(default=None, max_length=64)
    owner_id: str | None = None


class AllowListPatch(BaseModel):
    scope: str | None = Field(default=None, pattern="^(tenant|endpoint|tool)$")
    expires_at: datetime | None = None
    reason_code: str | None = Field(default=None, max_length=64)
    owner_id: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=512)
    no_expiry_override: bool | None = None


class AllowListResponse(BaseModel):
    total: int
    items: list[AllowListEntryResponse]


# -- Allow-list endpoints --------------------------------------------------

@router.get("/allow-list", response_model=AllowListResponse)
@limiter.limit("60/minute")
def list_allow_list(
    request: Request,
    authorization: str | None = Depends(get_authorization),
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
        .filter(
            (AllowListEntry.expires_at == None) | (AllowListEntry.expires_at > datetime.now(timezone.utc))  # noqa: E711
        )
        .order_by(AllowListEntry.created_at.desc())
        .all()
    )

    return AllowListResponse(
        total=len(entries),
        items=[
            AllowListEntryResponse(
                id=e.id,
                tenant_id=e.tenant_id,
                pattern=e.pattern,
                pattern_type=e.pattern_type,
                description=e.description,
                created_by=e.created_by,
                created_at=e.created_at.isoformat() if e.created_at else "",
                expires_at=e.expires_at.isoformat() if e.expires_at else None,
                scope=e.scope,
                reason_code=e.reason_code,
                owner_id=e.owner_id,
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
    authorization: str | None = Depends(get_authorization),
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
        expires_at=body.expires_at,
        scope=body.scope,
        reason_code=body.reason_code,
        owner_id=body.owner_id,
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
            "scope": body.scope,
            "reason_code": body.reason_code,
            "expires_at": body.expires_at.isoformat() if body.expires_at else None,
        },
    )

    db.commit()
    db.refresh(entry)

    allow_list = get_active_allow_list_patterns(db, tenant_id)
    endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == tenant_id).all()
    for ep in endpoints:
        background_tasks.add_task(
            push_posture_to_agent,
            request,
            ep.id,
            ep.enforcement_posture,
            ep.auto_enforce_threshold,
            allow_list,
        )

    return AllowListEntryResponse(
        id=entry.id,
        tenant_id=entry.tenant_id,
        pattern=entry.pattern,
        pattern_type=entry.pattern_type,
        description=entry.description,
        created_by=entry.created_by,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
        expires_at=entry.expires_at.isoformat() if entry.expires_at else None,
        scope=entry.scope,
        reason_code=entry.reason_code,
        owner_id=entry.owner_id,
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
    authorization: str | None = Depends(get_authorization),
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

    allow_list = get_active_allow_list_patterns(db, auth.tenant_id)
    endpoints = db.query(Endpoint).filter(Endpoint.tenant_id == auth.tenant_id).all()
    for ep in endpoints:
        background_tasks.add_task(
            push_posture_to_agent,
            request,
            ep.id,
            ep.enforcement_posture,
            ep.auto_enforce_threshold,
            allow_list,
        )


@router.patch("/allow-list/{entry_id}", response_model=AllowListEntryResponse)
@limiter.limit("30/minute")
def patch_allow_list_entry(
    request: Request,
    entry_id: str,
    body: AllowListPatch,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Partially update an allow-list entry. Owner/admin only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    entry = db.query(AllowListEntry).filter(
        AllowListEntry.id == entry_id,
        strict_tenant_filter(auth, AllowListEntry),
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Allow-list entry not found")

    before_snapshot = {
        "scope": entry.scope,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "reason_code": entry.reason_code,
        "owner_id": entry.owner_id,
        "description": entry.description,
        "no_expiry_override": getattr(entry, "no_expiry_override", False),
    }

    update_data = body.model_dump(exclude_unset=True)
    for field_name, value in update_data.items():
        if hasattr(entry, field_name):
            setattr(entry, field_name, value)

    after_snapshot = {
        "scope": entry.scope,
        "expires_at": entry.expires_at.isoformat() if entry.expires_at else None,
        "reason_code": entry.reason_code,
        "owner_id": entry.owner_id,
        "description": entry.description,
        "no_expiry_override": getattr(entry, "no_expiry_override", False),
    }

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="enforcement.allow_list_updated",
        resource_type="allow_list_entry",
        resource_id=entry.id,
        detail={"before": before_snapshot, "after": after_snapshot},
    )

    db.commit()
    db.refresh(entry)

    return AllowListEntryResponse(**serialize_allow_list_entry(entry))
