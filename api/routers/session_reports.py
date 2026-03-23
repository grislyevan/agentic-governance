"""Session reports router: agent session summaries from detection events."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from sqlalchemy.orm import Session

from core.database import get_db
from core.demo_session import DEMO_SESSION_ID, get_canned_demo_session
from core.session_aggregation import (
    DEFAULT_SESSION_GAP_MINUTES,
    aggregate_events_into_sessions,
    default_session_lookback_window,
    fetch_events_for_sessions,
    get_session_report_by_id,
    session_exists_by_session_id,
)
from core.auth_cookies import get_authorization
from core.tenant import get_tenant_filter, resolve_auth
from models.event import Event
from schemas.session_report import SessionReport, SessionReportListResponse

router = APIRouter(prefix="/session-reports", tags=["session-reports"])


@router.get("", response_model=SessionReportListResponse)
def list_session_reports(
    endpoint_id: str | None = Query(default=None, description="Filter by endpoint"),
    since: datetime | None = Query(default=None, description="Events after this time (ISO8601)"),
    before: datetime | None = Query(default=None, description="Events before this time (ISO8601)"),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> SessionReportListResponse:
    """Return session reports derived from detection events.

    Sessions are built by grouping consecutive detection events for the same
    endpoint and tool within a time window (default 15 minutes). Action counts
    are N/A when using detection-only aggregation.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    tenant_filter = get_tenant_filter(auth, Event)

    observed_after = since
    observed_before = before
    if observed_after is None and observed_before is None:
        observed_after, observed_before = default_session_lookback_window()

    events = fetch_events_for_sessions(
        db, tenant_filter, endpoint_id=endpoint_id, observed_after=observed_after, observed_before=observed_before, limit=limit
    )
    reports = aggregate_events_into_sessions(
        events,
        session_gap_minutes=DEFAULT_SESSION_GAP_MINUTES,
        endpoint_id=endpoint_id,
    )
    return SessionReportListResponse(items=reports)


@router.get("/{session_id}", response_model=SessionReport)
def get_session_report(
    session_id: str = Path(..., description="Synthetic session id from list response"),
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> SessionReport:
    """Return a single session report by id, or 404 if not found.
    When session_id is the canned demo id, returns the fixed demo session.
    Otherwise the session must fall within the configured lookback window (default last 7 days)
    and within the event limit (default 500 events); high-activity tenants may need higher
    SESSION_REPORT_BY_ID_EVENT_LIMIT or longer SESSION_LOOKBACK_DAYS.
    """
    auth = resolve_auth(authorization, x_api_key, db)
    if session_id == DEMO_SESSION_ID:
        return get_canned_demo_session()
    tenant_filter = get_tenant_filter(auth, Event)
    report = get_session_report_by_id(db, tenant_filter, session_id)
    if report is None:
        if session_exists_by_session_id(db, tenant_filter, session_id):
            raise HTTPException(
                status_code=410,
                detail="Session exists but cannot be reconstructed within the current event window. Try narrowing the time range.",
            )
        raise HTTPException(status_code=404, detail="Session report not found")
    return report
