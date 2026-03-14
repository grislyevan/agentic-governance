"""Endpoint profiles router: CRUD for tenant-scoped agent profiles."""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.database import get_db
from core.tenant import get_tenant_filter, resolve_auth, require_role
from models.endpoint_profile import EndpointProfile
from schemas.endpoint_profiles import (
    EndpointProfileCreate,
    EndpointProfileListResponse,
    EndpointProfileResponse,
    EndpointProfileUpdate,
)

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/endpoint-profiles", tags=["endpoint-profiles"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "profile"


@router.get("", response_model=EndpointProfileListResponse)
def list_profiles(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointProfileListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    q = db.query(EndpointProfile).filter(get_tenant_filter(auth, EndpointProfile))
    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(EndpointProfile.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return EndpointProfileListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[EndpointProfileResponse.model_validate(p) for p in items],
    )


@router.post("", response_model=EndpointProfileResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_profile(
    request: Request,
    body: EndpointProfileCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointProfileResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    slug = body.slug or _slugify(body.name)
    existing = (
        db.query(EndpointProfile)
        .filter(EndpointProfile.tenant_id == auth.tenant_id, EndpointProfile.slug == slug)
        .first()
    )
    if existing:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    profile = EndpointProfile(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        name=body.name,
        slug=slug,
        scan_interval_seconds=body.scan_interval_seconds,
        enforcement_posture=body.enforcement_posture,
        auto_enforce_threshold=body.auto_enforce_threshold,
        policy_set_id=body.policy_set_id,
    )
    db.add(profile)
    db.flush()
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint_profile.created",
        resource_type="endpoint_profile",
        resource_id=profile.id,
        detail={"name": body.name, "slug": profile.slug},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(profile)
    return EndpointProfileResponse.model_validate(profile)


@router.get("/{profile_id}", response_model=EndpointProfileResponse)
def get_profile(
    profile_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointProfileResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    profile = (
        db.query(EndpointProfile)
        .filter(EndpointProfile.id == profile_id, get_tenant_filter(auth, EndpointProfile))
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return EndpointProfileResponse.model_validate(profile)


@router.patch("/{profile_id}", response_model=EndpointProfileResponse)
@limiter.limit("20/minute")
def update_profile(
    request: Request,
    profile_id: str,
    body: EndpointProfileUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EndpointProfileResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    profile = (
        db.query(EndpointProfile)
        .filter(EndpointProfile.id == profile_id, EndpointProfile.tenant_id == auth.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    changes = body.model_dump(exclude_unset=True)

    if "slug" in changes and changes["slug"] is not None:
        other = (
            db.query(EndpointProfile)
            .filter(
                EndpointProfile.tenant_id == auth.tenant_id,
                EndpointProfile.slug == changes["slug"],
                EndpointProfile.id != profile_id,
            )
            .first()
        )
        if other:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Another profile already uses this slug",
            )

    for key, value in changes.items():
        setattr(profile, key, value)

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint_profile.updated",
        resource_type="endpoint_profile",
        resource_id=profile_id,
        detail={"changes": list(changes.keys())},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(profile)
    return EndpointProfileResponse.model_validate(profile)


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_profile(
    request: Request,
    profile_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    profile = (
        db.query(EndpointProfile)
        .filter(EndpointProfile.id == profile_id, EndpointProfile.tenant_id == auth.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")

    from models.endpoint import Endpoint
    assigned = db.query(Endpoint).filter(Endpoint.endpoint_profile_id == profile_id).count()
    if assigned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete profile: {assigned} endpoint(s) are assigned. Unassign them first.",
        )

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="endpoint_profile.deleted",
        resource_type="endpoint_profile",
        resource_id=profile_id,
        detail={"name": profile.name, "slug": profile.slug},
        ip_address=request.client.host if request.client else None,
    )
    db.delete(profile)
    db.commit()
