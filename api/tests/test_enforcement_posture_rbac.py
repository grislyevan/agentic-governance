"""Tests for Task 11c: RBAC guards on enforcement posture endpoints.

Verifies that:
- Active posture requires owner role (admin gets 403).
- Passive/audit posture allows owner or admin.
- Viewer/analyst cannot change posture at all.
- Tenant-wide posture requires owner for any state.
"""

from __future__ import annotations

import os
import sys

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

import pytest
from tests.conftest import API, _auth_header, register_user

from core.database import get_db
from models.endpoint import Endpoint
from models.user import User


def _create_endpoint(client, auth_header: dict, hostname: str = "test-host") -> str:
    """Seed an endpoint directly via DB so posture tests have a target."""
    db = next(get_db())
    user = db.query(User).first()
    ep = Endpoint(
        tenant_id=user.tenant_id,
        hostname=hostname,
    )
    db.add(ep)
    db.commit()
    db.refresh(ep)
    return ep.id


def _set_user_role(email: str, role: str) -> None:
    db = next(get_db())
    user = db.query(User).filter(User.email == email).first()
    user.role = role
    db.commit()


# ---------------------------------------------------------------------------
# Endpoint posture RBAC
# ---------------------------------------------------------------------------

class TestEndpointPostureRBAC:
    def test_owner_can_set_active(self, client) -> None:
        tokens = register_user(client, "owner@test.com", tenant_name="RBAC Org")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        resp = client.put(
            f"{API}/enforcement/endpoints/{ep_id}/posture",
            json={"enforcement_posture": "active", "auto_enforce_threshold": 0.80},
            headers=header,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["enforcement_posture"] == "active"
        assert resp.json()["auto_enforce_threshold"] == 0.80

    def test_admin_cannot_set_active(self, client) -> None:
        tokens = register_user(client, "admin-rbac@test.com", tenant_name="RBAC Org 2")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        _set_user_role("admin-rbac@test.com", "admin")

        resp = client.put(
            f"{API}/enforcement/endpoints/{ep_id}/posture",
            json={"enforcement_posture": "active"},
            headers=header,
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    def test_admin_can_set_audit(self, client) -> None:
        tokens = register_user(client, "admin-audit@test.com", tenant_name="RBAC Org 3")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        _set_user_role("admin-audit@test.com", "admin")

        resp = client.put(
            f"{API}/enforcement/endpoints/{ep_id}/posture",
            json={"enforcement_posture": "audit"},
            headers=header,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["enforcement_posture"] == "audit"

    def test_admin_can_set_passive(self, client) -> None:
        tokens = register_user(client, "admin-pass@test.com", tenant_name="RBAC Org 4")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        _set_user_role("admin-pass@test.com", "admin")

        resp = client.put(
            f"{API}/enforcement/endpoints/{ep_id}/posture",
            json={"enforcement_posture": "passive"},
            headers=header,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["enforcement_posture"] == "passive"

    def test_analyst_cannot_set_any_posture(self, client) -> None:
        tokens = register_user(client, "analyst@test.com", tenant_name="RBAC Org 5")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        _set_user_role("analyst@test.com", "analyst")

        for posture in ("passive", "audit", "active"):
            resp = client.put(
                f"{API}/enforcement/endpoints/{ep_id}/posture",
                json={"enforcement_posture": posture},
                headers=header,
            )
            assert resp.status_code == 403, (
                f"Analyst should not be able to set {posture}, got {resp.status_code}"
            )

    def test_viewer_cannot_set_any_posture(self, client) -> None:
        tokens = register_user(client, "viewer-rbac@test.com", tenant_name="RBAC Org 6")
        header = _auth_header(tokens["access_token"])
        ep_id = _create_endpoint(client, header)

        _set_user_role("viewer-rbac@test.com", "viewer")

        resp = client.put(
            f"{API}/enforcement/endpoints/{ep_id}/posture",
            json={"enforcement_posture": "passive"},
            headers=header,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tenant posture RBAC
# ---------------------------------------------------------------------------

class TestTenantPostureRBAC:
    def test_owner_can_set_tenant_posture(self, client) -> None:
        tokens = register_user(client, "t-owner@test.com", tenant_name="Tenant RBAC 1")
        header = _auth_header(tokens["access_token"])

        resp = client.put(
            f"{API}/enforcement/tenant-posture",
            json={"enforcement_posture": "audit", "auto_enforce_threshold": 0.65},
            headers=header,
        )
        assert resp.status_code == 200, resp.text

    def test_admin_cannot_set_tenant_posture(self, client) -> None:
        tokens = register_user(client, "t-admin@test.com", tenant_name="Tenant RBAC 2")
        header = _auth_header(tokens["access_token"])

        _set_user_role("t-admin@test.com", "admin")

        resp = client.put(
            f"{API}/enforcement/tenant-posture",
            json={"enforcement_posture": "passive"},
            headers=header,
        )
        assert resp.status_code == 403

    def test_analyst_cannot_set_tenant_posture(self, client) -> None:
        tokens = register_user(client, "t-analyst@test.com", tenant_name="Tenant RBAC 3")
        header = _auth_header(tokens["access_token"])

        _set_user_role("t-analyst@test.com", "analyst")

        resp = client.put(
            f"{API}/enforcement/tenant-posture",
            json={"enforcement_posture": "passive"},
            headers=header,
        )
        assert resp.status_code == 403
