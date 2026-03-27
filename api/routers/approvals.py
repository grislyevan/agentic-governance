"""Approvals router: manage approval_required decision lifecycle."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.auth_cookies import get_authorization
from core.database import get_db
from core.tenant import get_tenant_filter, require_role, resolve_auth, strict_tenant_filter
from models.approval_request import ApprovalRequest

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/approvals", tags=["approvals"])


# -- Schemas -----------------------------------------------------------------

class ApprovalRequestResponse(BaseModel):
    id: str
    tenant_id: str
    endpoint_id: str | None
    event_id: str | None
    tool_name: str | None
    tool_class: str | None
    confidence_band: str | None
    confidence_score: float | None
    policy_rule_id: str | None
    status: str
    requested_at: str
    requester_type: str
    decided_by: str | None
    decided_at: str | None
    reason: str | None

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    total: int
    items: list[ApprovalRequestResponse]


class ApprovalDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=1024)


class ApprovalCreate(BaseModel):
    endpoint_id: str | None = None
    event_id: str | None = None
    tool_name: str | None = None
    tool_class: str | None = None
    confidence_band: str | None = None
    confidence_score: float | None = None
    policy_rule_id: str | None = None


# -- Helpers -----------------------------------------------------------------

def _serialize(ar: ApprovalRequest) -> ApprovalRequestResponse:
    return ApprovalRequestResponse(
        id=ar.id,
        tenant_id=ar.tenant_id,
        endpoint_id=ar.endpoint_id,
        event_id=ar.event_id,
        tool_name=ar.tool_name,
        tool_class=ar.tool_class,
        confidence_band=ar.confidence_band,
        confidence_score=ar.confidence_score,
        policy_rule_id=ar.policy_rule_id,
        status=ar.status,
        requested_at=ar.requested_at.isoformat() if ar.requested_at else "",
        requester_type=ar.requester_type,
        decided_by=ar.decided_by,
        decided_at=ar.decided_at.isoformat() if ar.decided_at else None,
        reason=ar.reason,
    )


# -- Endpoints ---------------------------------------------------------------

@router.get("", response_model=ApprovalListResponse)
@limiter.limit("60/minute")
def list_approvals(
    request: Request,
    status_filter: str | None = Query(default=None, alias="status"),
    event_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """List approval requests for the tenant. Requires analyst role or higher."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    q = db.query(ApprovalRequest).filter(get_tenant_filter(auth, ApprovalRequest))

    if status_filter and status_filter != "all":
        q = q.filter(ApprovalRequest.status == status_filter)

    if event_id:
        q = q.filter(ApprovalRequest.event_id == event_id)

    q = q.order_by(ApprovalRequest.requested_at.desc()).limit(limit)
    items = q.all()

    return ApprovalListResponse(
        total=len(items),
        items=[_serialize(ar) for ar in items],
    )


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
@limiter.limit("60/minute")
def get_approval(
    request: Request,
    approval_id: str,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Get a single approval request. Requires analyst role or higher."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst")

    ar = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == approval_id,
        strict_tenant_filter(auth, ApprovalRequest),
    ).first()
    if not ar:
        raise HTTPException(status_code=404, detail="Approval request not found")

    return _serialize(ar)


@router.post("", response_model=ApprovalRequestResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_approval(
    request: Request,
    body: ApprovalCreate,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Create an approval request (agent or system triggered). No role restriction."""
    auth = resolve_auth(authorization, x_api_key, db)

    # Infer requester_type from auth role
    if auth.role == "agent":
        requester_type = "agent"
    elif auth.user_id:
        requester_type = "api"
    else:
        requester_type = "system"

    ar = ApprovalRequest(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        endpoint_id=body.endpoint_id,
        event_id=body.event_id,
        tool_name=body.tool_name,
        tool_class=body.tool_class,
        confidence_band=body.confidence_band,
        confidence_score=body.confidence_score,
        policy_rule_id=body.policy_rule_id,
        status="pending",
        requester_type=requester_type,
        requested_by=auth.user_id,
    )
    db.add(ar)
    db.commit()
    db.refresh(ar)

    return _serialize(ar)


@router.post("/{approval_id}/approve", response_model=ApprovalRequestResponse)
@limiter.limit("30/minute")
def approve_request(
    request: Request,
    approval_id: str,
    body: ApprovalDecision,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Approve a pending approval request. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ar = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == approval_id,
        strict_tenant_filter(auth, ApprovalRequest),
    ).with_for_update().first()
    if not ar:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if auth.user_id and auth.user_id == ar.requested_by:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot approve your own request",
        )

    if ar.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval request is already {ar.status}",
        )

    ar.status = "approved"
    ar.decided_by = auth.user_id
    ar.decided_at = datetime.now(timezone.utc)
    ar.reason = body.reason

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="approval.approved",
        resource_type="approval_request",
        resource_id=ar.id,
        detail={
            "tool_name": ar.tool_name,
            "policy_rule_id": ar.policy_rule_id,
            "reason": body.reason,
        },
    )

    db.commit()
    db.refresh(ar)

    return _serialize(ar)


@router.post("/{approval_id}/deny", response_model=ApprovalRequestResponse)
@limiter.limit("30/minute")
def deny_request(
    request: Request,
    approval_id: str,
    body: ApprovalDecision,
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Deny a pending approval request. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    ar = db.query(ApprovalRequest).filter(
        ApprovalRequest.id == approval_id,
        strict_tenant_filter(auth, ApprovalRequest),
    ).with_for_update().first()
    if not ar:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if auth.user_id and auth.user_id == ar.requested_by:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot deny your own request",
        )

    if ar.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Approval request is already {ar.status}",
        )

    ar.status = "denied"
    ar.decided_by = auth.user_id
    ar.decided_at = datetime.now(timezone.utc)
    ar.reason = body.reason

    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="approval.denied",
        resource_type="approval_request",
        resource_id=ar.id,
        detail={
            "tool_name": ar.tool_name,
            "policy_rule_id": ar.policy_rule_id,
            "reason": body.reason,
        },
    )

    db.commit()
    db.refresh(ar)

    return _serialize(ar)
