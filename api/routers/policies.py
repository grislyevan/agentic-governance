"""Policies router: view and manage tenant enforcement rules."""

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
from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.policy import Policy

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/policies", tags=["policies"])


class PolicyResponse(BaseModel):
    id: str
    rule_id: str
    rule_version: str
    description: str | None
    is_active: bool
    parameters: dict

    model_config = {"from_attributes": True}


class PolicyCreate(BaseModel):
    rule_id: str
    rule_version: str = "0.1.0"
    description: str | None = None
    parameters: dict = Field(default_factory=dict)


class PolicyListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PolicyResponse]


@router.get("", response_model=PolicyListResponse)
def list_policies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    tenant_id = auth.tenant_id
    q = db.query(Policy).filter(Policy.tenant_id == tenant_id)
    total = q.with_entities(func.count()).scalar() or 0
    items = q.order_by(Policy.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
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
    require_role(auth, "admin")
    policy = Policy(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        rule_id=body.rule_id,
        rule_version=body.rule_version,
        description=body.description,
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
    body: PolicyCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "admin")
    policy = db.query(Policy).filter(
        Policy.id == policy_id, Policy.tenant_id == auth.tenant_id
    ).first()
    if not policy:
        logger.warning("Policy %s not found for tenant %s", policy_id, auth.tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    old_rule_id = policy.rule_id
    policy.rule_id = body.rule_id
    policy.rule_version = body.rule_version
    policy.description = body.description
    policy.parameters = body.parameters
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="policy.updated",
        resource_type="policy",
        resource_id=policy_id,
        detail={"old_rule_id": old_rule_id, "new_rule_id": body.rule_id},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)
