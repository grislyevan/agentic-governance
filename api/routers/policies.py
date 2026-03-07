"""Policies router: view and manage tenant enforcement rules."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
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
    parameters: dict = {}


@router.get("", response_model=list[PolicyResponse])
def list_policies(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> list[PolicyResponse]:
    tenant_id = _get_tenant_id(authorization, x_api_key, db)
    items = db.query(Policy).filter(Policy.tenant_id == tenant_id).all()
    return [PolicyResponse.model_validate(p) for p in items]


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
