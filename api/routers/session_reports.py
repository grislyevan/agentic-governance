"""Session reports router: agent session summaries from detection events."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.session_aggregation import (
    DEFAULT_SESSION_GAP_MINUTES,
    aggregate_events_into_sessions,
    fetch_events_for_sessions,
)
from core.tenant import get_tenant_filter, resolve_auth
from models.event import Event
from schemas.session_report import SessionReportListResponse

router = APIRouter(prefix="/session-reports", tags=["session-reports"])


@router.get("", response_model=SessionReportListResponse)
def list_session_reports(
    endpoint_id: str | None = Query(default=None, description="Filter by endpoint"),
    since: datetime | None = Query(default=None, description="Events after this time (ISO8601)"),
    before: datetime | None = Query(default=None, description="Events before this time (ISO8601)"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> SessionReportListResponse:
    """Return session reports derived from detection events.

    Sessions are built by grouping consecutive detection events for the same
    endpoint and tool within a time window (default 15 minutes). Action counts
    are N/A when using detection-only aggregation.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    tenant_filter = get_tenant_filter(auth, Event)

    events = fetch_events_for_sessions(
        db, tenant_filter, endpoint_id=endpoint_id, observed_after=since, observed_before=before, limit=limit
    )
    reports = aggregate_events_into_sessions(
        events,
        session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES,
        endpoint_id=endpoint_id,
    )
    return SessionReportListResponse(items=reports)
