"""Retention settings router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.tenant import Tenant

router = APIRouter(prefix="/retention", tags=["retention"])


class RetentionSettingsResponse(BaseModel):
    retention_days: int


class RetentionSettingsUpdate(BaseModel):
    retention_days: int = Field(ge=7, le=365)


@router.get("/settings", response_model=RetentionSettingsResponse)
def get_retention_settings(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> RetentionSettingsResponse:
    """Return current tenant retention_days. Admin or owner."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    days = tenant.retention_days if tenant.retention_days is not None else settings.default_retention_days
    return RetentionSettingsResponse(retention_days=days)


@router.put("/settings", response_model=RetentionSettingsResponse)
def update_retention_settings(
    body: RetentionSettingsUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> RetentionSettingsResponse:
    """Update tenant retention_days. Owner only."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    tenant.retention_days = body.retention_days
    db.commit()
    db.refresh(tenant)
    return RetentionSettingsResponse(retention_days=tenant.retention_days)
