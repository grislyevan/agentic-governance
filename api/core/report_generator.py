"""Compliance report generator.

Produces structured compliance reports covering:
- Endpoint inventory and posture
- Event summary by type, tool, and severity
- Policy coverage and enforcement stats
- User access audit trail
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.audit import AuditLog
from models.endpoint import Endpoint
from models.event import Event
from models.policy import Policy
from models.tenant import Tenant
from models.user import User


def generate_compliance_report(
    db: Session,
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """Generate a structured compliance report for the given tenant and date range."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    tenant_name = tenant.name if tenant else "Unknown"

    report_id = str(uuid.uuid4())
    generated_at = datetime.now(timezone.utc)

    # Endpoint summary
    endpoints = (
        db.query(Endpoint)
        .filter(Endpoint.tenant_id == tenant_id)
        .all()
    )
    by_posture: dict[str, int] = {}
    by_platform: dict[str, int] = {}
    stale_count = 0
    for ep in endpoints:
        by_posture[ep.enforcement_posture] = by_posture.get(ep.enforcement_posture, 0) + 1
        platform = (ep.os_info or "unknown").split()[0] if ep.os_info else "unknown"
        by_platform[platform] = by_platform.get(platform, 0) + 1
        if ep.is_stale:
            stale_count += 1

    # Event summary (in date range)
    event_q = (
        db.query(Event)
        .filter(
            Event.tenant_id == tenant_id,
            Event.observed_at >= start_date,
            Event.observed_at <= end_date,
        )
    )
    events = event_q.all()

    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_tool: dict[str, int] = {}
    for ev in events:
        by_type[ev.event_type] = by_type.get(ev.event_type, 0) + 1
        if ev.severity_level:
            by_severity[ev.severity_level] = by_severity.get(ev.severity_level, 0) + 1
        if ev.tool_name:
            by_tool[ev.tool_name] = by_tool.get(ev.tool_name, 0) + 1

    # Policy summary
    policies = db.query(Policy).filter(Policy.tenant_id == tenant_id).all()
    active_count = sum(1 for p in policies if p.is_active)
    inactive_count = len(policies) - active_count

    by_rule: dict[str, int] = {}
    for ev in events:
        if ev.rule_id:
            by_rule[ev.rule_id] = by_rule.get(ev.rule_id, 0) + 1
    top_rules = sorted(by_rule.items(), key=lambda x: -x[1])[:10]

    # Enforcement summary (from events with enforcement payload)
    enf_total = 0
    by_tactic: dict[str, int] = {}
    simulated_count = 0
    applied_count = 0
    success_count = 0
    for ev in events:
        if ev.event_type in (
            "enforcement.applied",
            "enforcement.simulated",
            "enforcement.escalated",
            "enforcement.failed",
        ):
            enf_total += 1
            payload = ev.payload or {}
            enf = payload.get("enforcement") or payload
            tactic = enf.get("tactic") or "unknown"
            by_tactic[tactic] = by_tactic.get(tactic, 0) + 1
            if ev.event_type == "enforcement.simulated":
                simulated_count += 1
            else:
                applied_count += 1
            if enf.get("success") is True:
                success_count += 1

    success_rate = (success_count / applied_count * 100) if applied_count else 0.0

    # User access summary
    users = db.query(User).filter(User.tenant_id == tenant_id, User.is_active.is_(True)).all()
    by_role: dict[str, int] = {}
    for u in users:
        by_role[u.role] = by_role.get(u.role, 0) + 1

    thirty_days_ago = generated_at - timedelta(days=30)
    recent_logins = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action == "user.login",
            AuditLog.occurred_at >= thirty_days_ago,
        )
        .scalar()
    ) or 0

    password_resets = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.action.in_(["password.reset_requested", "password.reset_completed"]),
            AuditLog.occurred_at >= thirty_days_ago,
        )
        .scalar()
    ) or 0

    # Compliance posture
    audit_or_active = by_posture.get("audit", 0) + by_posture.get("active", 0)
    total_eps = len(endpoints)
    posture_pct = (audit_or_active / total_eps * 100) if total_eps else 0.0
    policy_coverage = (active_count / len(policies) * 100) if policies else 0.0

    return {
        "report_metadata": {
            "report_id": report_id,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "generated_at": generated_at.isoformat(),
        },
        "endpoint_summary": {
            "total": total_eps,
            "by_posture": by_posture,
            "by_platform": by_platform,
            "stale_count": stale_count,
        },
        "event_summary": {
            "total": len(events),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_tool": by_tool,
        },
        "policy_summary": {
            "total": len(policies),
            "active": active_count,
            "inactive": inactive_count,
            "enforcement_actions_by_rule_id": by_rule,
            "top_triggered_rules": [{"rule_id": r, "count": c} for r, c in top_rules],
        },
        "enforcement_summary": {
            "total": enf_total,
            "by_tactic": by_tactic,
            "simulated": simulated_count,
            "applied": applied_count,
            "success_rate_pct": round(success_rate, 1),
        },
        "user_access_summary": {
            "total_users": len(users),
            "by_role": by_role,
            "recent_logins_30d": recent_logins,
            "password_resets_30d": password_resets,
        },
        "compliance_posture": {
            "endpoints_audit_or_active_pct": round(posture_pct, 1),
            "policy_coverage_pct": round(policy_coverage, 1),
            "total_events_in_period": len(events),
        },
    }


def generate_csv_report(
    db: Session,
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
) -> bytes:
    """Generate CSV content with one row per event in the date range."""
    events = (
        db.query(Event)
        .filter(
            Event.tenant_id == tenant_id,
            Event.observed_at >= start_date,
            Event.observed_at <= end_date,
        )
        .order_by(Event.observed_at)
        .all()
    )

    ep_ids = {ev.endpoint_id for ev in events if ev.endpoint_id}
    ep_map: dict[str, str] = {}
    if ep_ids:
        for ep in db.query(Endpoint).filter(Endpoint.id.in_(ep_ids)).all():
            ep_map[ep.id] = ep.hostname or ""

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "event_id",
        "event_type",
        "observed_at",
        "tool_name",
        "tool_class",
        "decision_state",
        "severity_level",
        "endpoint_hostname",
        "rule_id",
    ])

    for ev in events:
        hostname = ep_map.get(ev.endpoint_id, "") if ev.endpoint_id else ""
        writer.writerow([
            ev.event_id or ev.id,
            ev.event_type or "",
            ev.observed_at.isoformat() if ev.observed_at else "",
            ev.tool_name or "",
            ev.tool_class or "",
            ev.decision_state or "",
            ev.severity_level or "",
            hostname,
            ev.rule_id or "",
        ])

    return buffer.getvalue().encode("utf-8")


def generate_pdf_report(report_data: dict[str, Any]) -> bytes:
    """Generate a formatted PDF from report data using reportlab."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        name="ReportTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=16,
        spaceAfter=8,
    )

    meta = report_data.get("report_metadata", {})
    tenant_name = meta.get("tenant_name", "Unknown")
    start = meta.get("start_date", "")[:10]
    end = meta.get("end_date", "")[:10]

    story = []
    story.append(Paragraph("Detec Compliance Report", title_style))
    story.append(Paragraph(f"Tenant: {tenant_name}", styles["Normal"]))
    story.append(Paragraph(f"Report Period: {start} to {end}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {meta.get('generated_at', '')[:19]} UTC", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))

    # Endpoint summary
    story.append(Paragraph("Endpoint Summary", heading_style))
    ep_sum = report_data.get("endpoint_summary", {})
    ep_data = [
        ["Metric", "Value"],
        ["Total Endpoints", str(ep_sum.get("total", 0))],
        ["By Posture", str(ep_sum.get("by_posture", {}))],
        ["Stale Endpoints", str(ep_sum.get("stale_count", 0))],
    ]
    t = Table(ep_data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    # Event summary
    story.append(Paragraph("Event Summary", heading_style))
    ev_sum = report_data.get("event_summary", {})
    ev_data = [
        ["Metric", "Value"],
        ["Total Events", str(ev_sum.get("total", 0))],
        ["By Type", str(ev_sum.get("by_type", {}))],
        ["By Severity", str(ev_sum.get("by_severity", {}))],
    ]
    t2 = Table(ev_data, colWidths=[3 * inch, 3 * inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.2 * inch))

    # Policy summary
    story.append(Paragraph("Policy Summary", heading_style))
    pol_sum = report_data.get("policy_summary", {})
    pol_data = [
        ["Metric", "Value"],
        ["Total Policies", str(pol_sum.get("total", 0))],
        ["Active", str(pol_sum.get("active", 0))],
        ["Inactive", str(pol_sum.get("inactive", 0))],
    ]
    t3 = Table(pol_data, colWidths=[3 * inch, 3 * inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.2 * inch))

    # Enforcement summary
    story.append(Paragraph("Enforcement Summary", heading_style))
    enf_sum = report_data.get("enforcement_summary", {})
    enf_data = [
        ["Metric", "Value"],
        ["Total Enforcements", str(enf_sum.get("total", 0))],
        ["Simulated", str(enf_sum.get("simulated", 0))],
        ["Applied", str(enf_sum.get("applied", 0))],
        ["Success Rate (%)", str(enf_sum.get("success_rate_pct", 0))],
    ]
    t4 = Table(enf_data, colWidths=[3 * inch, 3 * inch])
    t4.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t4)
    story.append(Spacer(1, 0.2 * inch))

    # User access summary
    story.append(Paragraph("User Access Summary", heading_style))
    user_sum = report_data.get("user_access_summary", {})
    user_data = [
        ["Metric", "Value"],
        ["Total Users", str(user_sum.get("total_users", 0))],
        ["By Role", str(user_sum.get("by_role", {}))],
        ["Recent Logins (30d)", str(user_sum.get("recent_logins_30d", 0))],
        ["Password Resets (30d)", str(user_sum.get("password_resets_30d", 0))],
    ]
    t5 = Table(user_data, colWidths=[3 * inch, 3 * inch])
    t5.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t5)
    story.append(Spacer(1, 0.2 * inch))

    # Compliance posture
    story.append(Paragraph("Compliance Posture", heading_style))
    comp = report_data.get("compliance_posture", {})
    comp_data = [
        ["Metric", "Value"],
        ["Endpoints Audit/Active (%)", str(comp.get("endpoints_audit_or_active_pct", 0))],
        ["Policy Coverage (%)", str(comp.get("policy_coverage_pct", 0))],
        ["Events in Period", str(comp.get("total_events_in_period", 0))],
    ]
    t6 = Table(comp_data, colWidths=[3 * inch, 3 * inch])
    t6.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(t6)

    doc.build(story)
    return buffer.getvalue()
