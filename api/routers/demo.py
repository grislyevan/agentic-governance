"""Demo mode router: status check and data reset for sales demos."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.endpoint import Endpoint
from models.event import Event

router = APIRouter(prefix="/demo", tags=["demo"])


class DemoStatusResponse(BaseModel):
    demo_mode: bool
    endpoints: int = 0
    events: int = 0
    last_reset: str | None = None


class DemoResetResponse(BaseModel):
    status: str
    endpoints: int
    events: int


@router.get("/status", response_model=DemoStatusResponse)
def demo_status(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> DemoStatusResponse:
    """Return demo mode state and data counts."""
    if not settings.demo_mode:
        return DemoStatusResponse(demo_mode=False)

    auth = resolve_auth(authorization, x_api_key, db)
    ep_count = (
        db.query(func.count(Endpoint.id))
        .filter(Endpoint.tenant_id == auth.tenant_id)
        .scalar()
    ) or 0
    ev_count = (
        db.query(func.count(Event.id))
        .filter(Event.tenant_id == auth.tenant_id)
        .scalar()
    ) or 0

    return DemoStatusResponse(
        demo_mode=True,
        endpoints=ep_count,
        events=ev_count,
        last_reset=datetime.now(timezone.utc).isoformat(),
    )


@router.post("/reset", response_model=DemoResetResponse)
def demo_reset(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> DemoResetResponse:
    """Wipe and re-seed demo data. Owner only. Returns 403 when not in demo mode."""
    if not settings.demo_mode:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo mode is not enabled",
        )

    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")

    from core.demo_seed import clear_demo_data, seed_demo_data

    clear_demo_data(db, auth.tenant_id)
    n_endpoints, n_events = seed_demo_data(db, auth.tenant_id)
    db.commit()

    return DemoResetResponse(
        status="reset",
        endpoints=n_endpoints,
        events=n_events,
    )
