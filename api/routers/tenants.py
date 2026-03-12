"""Tenant (organization) management: list, create, update, switch."""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.auth import create_access_token, create_refresh_token
from core.database import get_db
from core.tenant import resolve_auth, require_role, AuthContext
from models.endpoint import Endpoint
from models.tenant import Tenant, generate_agent_key
from models.tenant_membership import TenantMembership
from models.user import User
from schemas.tenants import (
    TenantCreate,
    TenantOut,
    TenantSwitchRequest,
    TenantSwitchResponse,
    TenantUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "tenant"


def _tenant_to_out(tenant: Tenant, db: Session, role: str | None = None) -> TenantOut:
    member_count = (
        db.query(sa_func.count(TenantMembership.id))
        .filter(TenantMembership.tenant_id == tenant.id)
        .scalar() or 0
    )
    endpoint_count = (
        db.query(sa_func.count(Endpoint.id))
        .filter(Endpoint.tenant_id == tenant.id)
        .scalar() or 0
    )
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        subscription_tier=tenant.subscription_tier,
        member_count=member_count,
        endpoint_count=endpoint_count,
        created_at=tenant.created_at,
        role=role,
    )


def _auth(authorization, x_api_key, db) -> AuthContext:
    return resolve_auth(authorization, x_api_key, db)


def _ensure_membership(db: Session, user_id: str, tenant_id: str, role: str) -> None:
    """Create a membership if one doesn't already exist."""
    existing = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user_id,
            TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if not existing:
        db.add(TenantMembership(
            id=str(uuid.uuid4()),
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
        ))


@router.get("/current", response_model=TenantOut)
def get_current_tenant(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> TenantOut:
    """Get details of the authenticated user's current tenant."""
    auth = _auth(authorization, x_api_key, db)
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_to_out(tenant, db, role=auth.role)


@router.get("/mine", response_model=list[TenantOut])
def list_my_tenants(
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> list[TenantOut]:
    """List all tenants where the current user has a membership."""
    auth = _auth(authorization, x_api_key, db)

    memberships = (
        db.query(TenantMembership)
        .filter(TenantMembership.user_id == auth.user_id)
        .all()
    )

    if not memberships:
        tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
        if tenant:
            _ensure_membership(db, auth.user_id, auth.tenant_id, auth.role or "owner")
            db.commit()
            return [_tenant_to_out(tenant, db, role=auth.role)]
        return []

    role_by_tenant = {m.tenant_id: m.role for m in memberships}
    tenant_ids = list(role_by_tenant.keys())
    tenants = db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).all()
    return [
        _tenant_to_out(t, db, role=role_by_tenant.get(t.id))
        for t in sorted(tenants, key=lambda t: t.created_at)
    ]


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    request: Request,
    body: TenantCreate,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> TenantOut:
    """Create a new organization. The caller becomes owner via a membership record."""
    auth = _auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant_name = body.name
    slug = _slugify(body.name)

    existing_name = db.query(Tenant).filter(Tenant.name == tenant_name).first()
    if existing_name:
        suffix = uuid.uuid4().hex[:6]
        tenant_name = f"{body.name} ({suffix})"

    existing_slug = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing_slug:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=tenant_name,
        slug=slug,
        agent_key=generate_agent_key(),
    )
    db.add(tenant)
    db.flush()

    membership = TenantMembership(
        id=str(uuid.uuid4()),
        user_id=auth.user_id,
        tenant_id=tenant.id,
        role="owner",
    )
    db.add(membership)

    from core.baseline_policies import seed_baseline_policies
    seed_baseline_policies(db, tenant.id)

    audit_record(
        db,
        tenant_id=tenant.id,
        actor_id=auth.user_id,
        action="tenant.created",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"name": body.name, "source_tenant_id": auth.tenant_id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    logger.info("Tenant '%s' created by user %s", tenant.name, auth.user_id)
    return _tenant_to_out(tenant, db, role="owner")


@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: str,
    body: TenantUpdate,
    request: Request,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> TenantOut:
    """Update tenant name. Owner only."""
    auth = _auth(authorization, x_api_key, db)

    membership = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == auth.user_id,
            TenantMembership.tenant_id == tenant_id,
        )
        .first()
    )
    if not membership or membership.role != "owner":
        raise HTTPException(status_code=403, detail="Only the owner can update a tenant")

    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if body.name is not None:
        tenant.name = body.name
        new_slug = _slugify(body.name)
        conflict = db.query(Tenant).filter(Tenant.slug == new_slug, Tenant.id != tenant_id).first()
        if conflict:
            new_slug = f"{new_slug}-{uuid.uuid4().hex[:6]}"
        tenant.slug = new_slug

    audit_record(
        db,
        tenant_id=tenant.id,
        actor_id=auth.user_id,
        action="tenant.updated",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"changes": body.model_dump(exclude_unset=True)},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return _tenant_to_out(tenant, db, role=membership.role)


@router.post("/switch", response_model=TenantSwitchResponse)
def switch_tenant(
    body: TenantSwitchRequest,
    request: Request,
    authorization: str | None = Header(None),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
    db: Session = Depends(get_db),
) -> TenantSwitchResponse:
    """Switch to a different tenant. The user must have a membership there."""
    auth = _auth(authorization, x_api_key, db)

    membership = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == auth.user_id,
            TenantMembership.tenant_id == body.tenant_id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=403, detail="No membership in target organization")

    tenant = db.query(Tenant).filter(Tenant.id == body.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    user = db.query(User).filter(User.id == auth.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    refresh_tok, refresh_jti = create_refresh_token(user.id, tenant.id)
    user.refresh_jti = refresh_jti

    audit_record(
        db,
        tenant_id=tenant.id,
        actor_id=user.id,
        action="tenant.switched",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"from_tenant_id": auth.tenant_id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    logger.info("User %s switched to tenant '%s'", user.email, tenant.name)
    return TenantSwitchResponse(
        access_token=create_access_token(user.id, tenant.id),
        refresh_token=refresh_tok,
        tenant=_tenant_to_out(tenant, db, role=membership.role),
    )
