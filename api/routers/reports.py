"""Reports router: compliance report generation and summary."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.report_generator import (
    generate_compliance_report,
    generate_csv_report,
    generate_pdf_report,
)
from core.tenant import resolve_auth, require_role

router = APIRouter(prefix="/reports", tags=["reports"])


class ComplianceReportRequest(BaseModel):
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    format: str = Field(default="json", pattern="^(json|csv|pdf)$")


def _parse_date(s: str) -> datetime:
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(400, f"Invalid date format: {s}. Use YYYY-MM-DD.")


@router.post("/compliance")
def generate_compliance(
    body: ComplianceReportRequest,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Generate a compliance report. Owner or admin only.

    Formats: json (returns JSON), csv (file download), pdf (file download).
    """
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    start_date = _parse_date(body.start_date)
    end_date = _parse_date(body.end_date)
    if end_date < start_date:
        raise HTTPException(400, "end_date must be >= start_date")

    if body.format == "json":
        report = generate_compliance_report(db, auth.tenant_id, start_date, end_date)
        return report

    report_data = generate_compliance_report(db, auth.tenant_id, start_date, end_date)

    if body.format == "csv":
        content = generate_csv_report(db, auth.tenant_id, start_date, end_date)
        filename = f"detec-compliance-{body.start_date}-{body.end_date}.csv"
        return StreamingResponse(
            iter([content]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    if body.format == "pdf":
        content = generate_pdf_report(report_data)
        filename = f"detec-compliance-{body.start_date}-{body.end_date}.pdf"
        return StreamingResponse(
            iter([content]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(400, f"Unknown format: {body.format}")


@router.get("/compliance/summary")
def compliance_summary(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Quick compliance summary for the last 30 days. Any authenticated user."""
    auth = resolve_auth(authorization, x_api_key, db)

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=30)

    report = generate_compliance_report(db, auth.tenant_id, start_date, end_date)

    return {
        "endpoints_total": report["endpoint_summary"]["total"],
        "endpoints_stale": report["endpoint_summary"]["stale_count"],
        "events_total": report["event_summary"]["total"],
        "policies_active": report["policy_summary"]["active"],
        "enforcements_total": report["enforcement_summary"]["total"],
        "compliance_score_pct": report["compliance_posture"]["endpoints_audit_or_active_pct"],
    }
