"""Tests for the compliance reports endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import API, _auth_header, login_user, register_user


def _owner_headers(client):
    register_user(client, email="owner@reports.com", password="reportpass123", tenant_name="ReportTenant")
    tokens = login_user(client, email="owner@reports.com", password="reportpass123")
    return _auth_header(tokens["access_token"])


def _analyst_headers(client):
    register_user(client, email="analyst@reports.com", password="reportpass123", tenant_name="ReportTenant2")
    tokens = login_user(client, email="analyst@reports.com", password="reportpass123")
    from core.database import get_db
    from models.user import User
    db = next(get_db())
    user = db.query(User).filter(User.email == "analyst@reports.com").first()
    user.role = "analyst"
    db.commit()
    return _auth_header(tokens["access_token"])


class TestComplianceReport:
    def test_json_format_returns_expected_structure(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "report_metadata" in data
        assert data["report_metadata"]["start_date"].startswith("2026-01-01")
        assert data["report_metadata"]["end_date"].startswith("2026-03-12")
        assert "tenant_name" in data["report_metadata"]
        assert "report_id" in data["report_metadata"]
        assert "endpoint_summary" in data
        assert "total" in data["endpoint_summary"]
        assert "event_summary" in data
        assert "policy_summary" in data
        assert "enforcement_summary" in data
        assert "user_access_summary" in data
        assert "compliance_posture" in data

    def test_csv_format_returns_valid_csv(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "csv",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type", "").startswith("text/csv")
        lines = resp.text.strip().split("\n")
        assert len(lines) >= 1
        assert "event_id,event_type,observed_at,tool_name" in lines[0] or "event_id" in lines[0]

    def test_pdf_format_returns_valid_pdf_bytes(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "pdf",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers.get("content-type", "").startswith("application/pdf")
        content = resp.content
        assert len(content) > 100
        assert content[:4] == b"%PDF"

    def test_date_range_filtering(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2025-06-01",
                "end_date": "2025-06-30",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["report_metadata"]["start_date"].startswith("2025-06-01")
        assert data["report_metadata"]["end_date"].startswith("2025-06-30")
        assert data["event_summary"]["total"] >= 0

    def test_invalid_date_format(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "invalid",
                "end_date": "2026-03-12",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 400, resp.text

    def test_end_date_before_start_date(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-03-12",
                "end_date": "2026-01-01",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 400, resp.text

    def test_owner_can_generate_report(self, client):
        headers = _owner_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 200, resp.text

    def test_analyst_cannot_generate_report(self, client):
        headers = _analyst_headers(client)
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "json",
            },
            headers=headers,
        )
        assert resp.status_code == 403, resp.text

    def test_report_requires_auth(self, client):
        resp = client.post(
            f"{API}/reports/compliance",
            json={
                "start_date": "2026-01-01",
                "end_date": "2026-03-12",
                "format": "json",
            },
        )
        assert resp.status_code == 401, resp.text


class TestComplianceSummary:
    def test_summary_returns_expected_keys(self, client):
        headers = _owner_headers(client)
        resp = client.get(f"{API}/reports/compliance/summary", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "endpoints_total" in data
        assert "endpoints_stale" in data
        assert "events_total" in data
        assert "policies_active" in data
        assert "enforcements_total" in data
        assert "compliance_score_pct" in data

    def test_summary_accessible_by_analyst(self, client):
        headers = _analyst_headers(client)
        resp = client.get(f"{API}/reports/compliance/summary", headers=headers)
        assert resp.status_code == 200, resp.text

    def test_summary_requires_auth(self, client):
        resp = client.get(f"{API}/reports/compliance/summary")
        assert resp.status_code == 401, resp.text
