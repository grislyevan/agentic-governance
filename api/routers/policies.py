"""Policies router: view and manage tenant enforcement rules."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.database import get_db
from core.tenant import get_tenant_id as _get_tenant_id
from models.policy import Policy

logger = logging.getLogger(__name__)

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
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    q = db.query(Policy).filter(Policy.tenant_id == tenant_id)
    total = q.with_entities(func.count()).scalar() or 0
    items = q.order_by(Policy.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return PolicyListResponse(
        total=total, page=page, page_size=page_size,
        items=[PolicyResponse.model_validate(p) for p in items],
    )


@router.post("", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
def create_policy(
    body: PolicyCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyResponse:
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    policy = Policy(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        rule_id=body.rule_id,
        rule_version=body.rule_version,
        description=body.description,
        parameters=body.parameters,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(
    policy_id: str,
    body: PolicyCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PolicyResponse:
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    policy = db.query(Policy).filter(
        Policy.id == policy_id, Policy.tenant_id == tenant_id
    ).first()
    if not policy:
        logger.warning("Policy %s not found for tenant %s", policy_id, tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    policy.rule_id = body.rule_id
    policy.rule_version = body.rule_version
    policy.description = body.description
    policy.parameters = body.parameters
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)
