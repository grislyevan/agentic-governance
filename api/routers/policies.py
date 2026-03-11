"""Policies router: view and manage tenant enforcement rules.

Baseline policies (``is_baseline=True``) are seeded on tenant creation.
They can be toggled on/off but cannot be deleted or have their rule_id
changed.  The ``POST /policies/restore-defaults`` endpoint re-creates
any missing baseline rules and resets them to their shipped state.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.baseline_policies import get_baseline_rule_ids, seed_baseline_policies
from core.database import get_db
from core.tenant import resolve_auth, require_role, get_tenant_filter
from models.policy import Policy

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/policies", tags=["policies"])

_BASELINE_IDS = get_baseline_rule_ids()

# ── Response / Request schemas ────────────────────────────────────────

class PolicyResponse(BaseModel):
    id: str
    rule_id: str
    rule_version: str
    description: str | None
    is_active: bool
    is_baseline: bool
    category: str | None
    parameters: dict

    model_config = {"from_attributes": True}


class PolicyCreate(BaseModel):
    rule_id: str = Field(max_length=128)
    rule_version: str = Field(default="0.4.0", max_length=32)
    description: str | None = Field(default=None, max_length=512)
    is_active: bool = True
    parameters: dict = Field(default_factory=dict)


class PolicyUpdate(BaseModel):
    rule_id: str | None = Field(default=None, max_length=128)
    rule_version: str | None = Field(default=None, max_length=32)
    description: str | None = None
    is_active: bool | None = None
    parameters: dict | None = None


class PolicyListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PolicyResponse]


class RestoreDefaultsResponse(BaseModel):
    restored: int
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────

@router.get("", response_model=PolicyListResponse)
def list_policies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    category: str | None = Query(default=None),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    q = db.query(Policy).filter(get_tenant_filter(auth, Policy))
    if category:
        q = q.filter(Policy.category == category)
    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(Policy.is_baseline.desc(), Policy.category, Policy.rule_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PolicyListResponse(
        total=total, page=page, page_size=page_size,
        items=[PolicyResponse.model_validate(p) for p in items],
    )


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
def create_policy(
    request: Request,
    body: PolicyCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    if body.rule_id in _BASELINE_IDS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Rule ID '{body.rule_id}' is reserved for baseline policies. "
                   "Use PATCH to modify or POST /policies/restore-defaults to reset.",
        )

    policy = Policy(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        rule_id=body.rule_id,
        rule_version=body.rule_version,
        description=body.description,
        is_active=body.is_active,
        is_baseline=False,
        parameters=body.parameters,
    )
    db.add(policy)
    db.flush()
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="policy.created",
        resource_type="policy",
        resource_id=policy.id,
        detail={"rule_id": body.rule_id, "rule_version": body.rule_version},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
@limiter.limit("20/minute")
def update_policy(
    request: Request,
    policy_id: str,
    body: PolicyUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    policy = db.query(Policy).filter(
        Policy.id == policy_id, Policy.tenant_id == auth.tenant_id,
    ).first()
    if not policy:
        logger.warning("Policy %s not found for tenant %s", policy_id, auth.tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    changes = body.model_dump(exclude_unset=True)

    if policy.is_baseline and "rule_id" in changes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot change rule_id on a baseline policy.",
        )

    old_rule_id = policy.rule_id
    for field_name, value in changes.items():
        setattr(policy, field_name, value)

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="policy.updated",
        resource_type="policy",
        resource_id=policy_id,
        detail={
            "old_rule_id": old_rule_id,
            "changes": list(changes.keys()),
            "is_baseline": policy.is_baseline,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.delete("/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
def delete_policy(
    request: Request,
    policy_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    policy = db.query(Policy).filter(
        Policy.id == policy_id, Policy.tenant_id == auth.tenant_id,
    ).first()
    if not policy:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")

    if policy.is_baseline:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Baseline policies cannot be deleted. Disable it instead, "
                   "or use POST /policies/restore-defaults to reset all baseline rules.",
        )

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="policy.deleted",
        resource_type="policy",
        resource_id=policy_id,
        detail={"rule_id": policy.rule_id},
        ip_address=request.client.host if request.client else None,
    )
    db.delete(policy)
    db.commit()


@router.post("/restore-defaults", response_model=RestoreDefaultsResponse)
@limiter.limit("5/minute")
def restore_defaults(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> RestoreDefaultsResponse:
    """Re-create missing baseline policies and reset existing ones to defaults."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    restored = seed_baseline_policies(db, auth.tenant_id, restore=True)
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="policy.restore_defaults",
        resource_type="policy",
        resource_id="baseline",
        detail={"restored_count": restored, "baseline_version": "0.4.0"},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    return RestoreDefaultsResponse(
        restored=restored,
        message=f"Baseline policies restored to v0.4.0 defaults. {restored} rules re-created.",
    )
