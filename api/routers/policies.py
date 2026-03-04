"""Policies router: view and manage tenant enforcement rules."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.auth import is_valid_token
from ..core.database import get_db
from ..models.policy import Policy
from ..models.user import User

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


def _get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    if authorization and authorization.startswith("Bearer "):
        payload = is_valid_token(authorization.removeprefix("Bearer ").strip())
        if payload:
            return payload["tenant_id"]
    if x_api_key:
        user = db.query(User).filter(User.api_key == x_api_key, User.is_active.is_(True)).first()
        if user:
            return user.tenant_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
    policy.rule_id = body.rule_id
    policy.rule_version = body.rule_version
    policy.description = body.description
    policy.parameters = body.parameters
    db.commit()
    db.refresh(policy)
    return PolicyResponse.model_validate(policy)
