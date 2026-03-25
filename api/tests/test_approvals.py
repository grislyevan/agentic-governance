"""Tests for the approval request lifecycle endpoints (G1)."""

from __future__ import annotations

import pytest
from tests.conftest import API, _auth_header, register_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_owner(client, email="appr-owner@test.com", tenant_name="Approvals Org"):
    tokens = register_user(client, email=email, tenant_name=tenant_name)
    return _auth_header(tokens["access_token"])


def _create_analyst(client, owner_header, email, password="testpass12345"):
    client.post(f"{API}/users", json={
        "email": email,
        "password": password,
        "first_name": "Analyst",
        "last_name": "User",
        "role": "analyst",
    }, headers=owner_header)
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return _auth_header(resp.json()["access_token"])


def _create_admin(client, owner_header, email, password="testpass12345"):
    client.post(f"{API}/users", json={
        "email": email,
        "password": password,
        "first_name": "Admin",
        "last_name": "User",
        "role": "admin",
    }, headers=owner_header)
    resp = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return _auth_header(resp.json()["access_token"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCreateApproval:
    def test_create_approval_request(self, client):
        """Owner (or any authenticated user) can create an approval request."""
        owner_header = _setup_owner(client)
        resp = client.post(f"{API}/approvals", json={
            "tool_name": "cursor",
            "confidence_band": "High",
            "confidence_score": 0.91,
            "policy_rule_id": "ENFORCE-003",
        }, headers=owner_header)
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["id"]
        assert data["status"] == "pending"
        assert data["tool_name"] == "cursor"
        assert data["confidence_band"] == "High"
        assert data["confidence_score"] == pytest.approx(0.91)
        assert data["policy_rule_id"] == "ENFORCE-003"
        assert data["decided_by"] is None
        assert data["decided_at"] is None

    def test_create_approval_minimal_body(self, client):
        """Approval request can be created with an empty body."""
        owner_header = _setup_owner(client)
        resp = client.post(f"{API}/approvals", json={}, headers=owner_header)
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending"

    def test_create_approval_requires_auth(self, client):
        resp = client.post(f"{API}/approvals", json={})
        assert resp.status_code == 401


class TestListApprovals:
    def test_list_approvals_analyst(self, client):
        """Analyst can list approval requests."""
        owner_header = _setup_owner(client)
        analyst_header = _create_analyst(client, owner_header, "list-analyst@test.com")

        # Create two requests as owner
        client.post(f"{API}/approvals", json={"tool_name": "tool-a"}, headers=owner_header)
        client.post(f"{API}/approvals", json={"tool_name": "tool-b"}, headers=owner_header)

        resp = client.get(f"{API}/approvals", headers=analyst_header)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    def test_list_approvals_filter_by_status(self, client):
        """Status filter returns only matching requests."""
        owner_header = _setup_owner(client)

        # Create two pending requests
        client.post(f"{API}/approvals", json={"tool_name": "tool-x"}, headers=owner_header)
        r2 = client.post(f"{API}/approvals", json={"tool_name": "tool-y"}, headers=owner_header)
        approval_id = r2.json()["id"]

        # Approve one
        client.post(f"{API}/approvals/{approval_id}/approve", json={}, headers=owner_header)

        resp = client.get(f"{API}/approvals?status=pending", headers=owner_header)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get(f"{API}/approvals?status=approved", headers=owner_header)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_approvals_requires_analyst_or_above(self, client):
        """Viewer role cannot list approvals."""
        owner_header = _setup_owner(client)
        client.post(f"{API}/users", json={
            "email": "viewer-appr@test.com",
            "password": "testpass12345",
            "first_name": "View",
            "last_name": "Er",
            "role": "viewer",
        }, headers=owner_header)
        login = client.post(f"{API}/auth/login", json={
            "email": "viewer-appr@test.com", "password": "testpass12345",
        })
        viewer_header = _auth_header(login.json()["access_token"])
        resp = client.get(f"{API}/approvals", headers=viewer_header)
        assert resp.status_code == 403


class TestGetApproval:
    def test_get_single_approval_analyst(self, client):
        """Analyst can fetch a single approval request."""
        owner_header = _setup_owner(client)
        analyst_header = _create_analyst(client, owner_header, "get-analyst@test.com")

        create_resp = client.post(f"{API}/approvals", json={"tool_name": "my-tool"}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        resp = client.get(f"{API}/approvals/{approval_id}", headers=analyst_header)
        assert resp.status_code == 200, resp.text
        assert resp.json()["id"] == approval_id
        assert resp.json()["tool_name"] == "my-tool"

    def test_get_nonexistent_approval(self, client):
        owner_header = _setup_owner(client)
        resp = client.get(f"{API}/approvals/does-not-exist", headers=owner_header)
        assert resp.status_code == 404


class TestApproveRequest:
    def test_approve_pending_request(self, client):
        """Admin can approve a pending request; status changes and decided_at is set."""
        owner_header = _setup_owner(client)
        admin_header = _create_admin(client, owner_header, "approving-admin@test.com")

        create_resp = client.post(f"{API}/approvals", json={"tool_name": "cursor"}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        resp = client.post(
            f"{API}/approvals/{approval_id}/approve",
            json={"reason": "Reviewed and approved"},
            headers=admin_header,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "approved"
        assert data["decided_by"] is not None
        assert data["decided_at"] is not None
        assert data["reason"] == "Reviewed and approved"

    def test_approve_creates_audit_log(self, client):
        """Approving a request writes an audit log entry."""
        owner_header = _setup_owner(client)
        admin_header = _create_admin(client, owner_header, "audit-admin@test.com")

        create_resp = client.post(f"{API}/approvals", json={"tool_name": "audit-tool"}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        client.post(
            f"{API}/approvals/{approval_id}/approve",
            json={"reason": "all good"},
            headers=admin_header,
        )

        audit_resp = client.get(f"{API}/audit-log", headers=owner_header)
        assert audit_resp.status_code == 200
        actions = [entry["action"] for entry in audit_resp.json()["items"]]
        assert "approval.approved" in actions


class TestDenyRequest:
    def test_deny_pending_request(self, client):
        """Admin can deny a pending request; status changes to denied."""
        owner_header = _setup_owner(client)
        admin_header = _create_admin(client, owner_header, "denying-admin@test.com")

        create_resp = client.post(f"{API}/approvals", json={"tool_name": "bad-tool"}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        resp = client.post(
            f"{API}/approvals/{approval_id}/deny",
            json={"reason": "Policy violation"},
            headers=admin_header,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "denied"
        assert data["decided_by"] is not None
        assert data["decided_at"] is not None
        assert data["reason"] == "Policy violation"


class TestDoubleDecision:
    def test_double_approve_fails_409(self, client):
        """Approving an already-approved request returns 409 Conflict."""
        owner_header = _setup_owner(client)

        create_resp = client.post(f"{API}/approvals", json={}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        client.post(f"{API}/approvals/{approval_id}/approve", json={}, headers=owner_header)
        resp = client.post(f"{API}/approvals/{approval_id}/approve", json={}, headers=owner_header)
        assert resp.status_code == 409, resp.text

    def test_deny_after_approve_fails_409(self, client):
        """Denying an already-approved request returns 409 Conflict."""
        owner_header = _setup_owner(client)

        create_resp = client.post(f"{API}/approvals", json={}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        client.post(f"{API}/approvals/{approval_id}/approve", json={}, headers=owner_header)
        resp = client.post(f"{API}/approvals/{approval_id}/deny", json={}, headers=owner_header)
        assert resp.status_code == 409, resp.text


class TestRbacApprovals:
    def test_analyst_cannot_approve(self, client):
        """Analyst role cannot approve requests — requires admin or owner."""
        owner_header = _setup_owner(client)
        analyst_header = _create_analyst(client, owner_header, "rbac-analyst@test.com")

        create_resp = client.post(f"{API}/approvals", json={}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        resp = client.post(
            f"{API}/approvals/{approval_id}/approve",
            json={},
            headers=analyst_header,
        )
        assert resp.status_code == 403

    def test_analyst_cannot_deny(self, client):
        """Analyst role cannot deny requests — requires admin or owner."""
        owner_header = _setup_owner(client)
        analyst_header = _create_analyst(client, owner_header, "rbac-analyst-deny@test.com")

        create_resp = client.post(f"{API}/approvals", json={}, headers=owner_header)
        approval_id = create_resp.json()["id"]

        resp = client.post(
            f"{API}/approvals/{approval_id}/deny",
            json={},
            headers=analyst_header,
        )
        assert resp.status_code == 403


class TestTenantIsolation:
    def test_approval_from_tenant_a_not_visible_to_tenant_b(self, client):
        """Approval request created in tenant A is not visible to analyst in tenant B."""
        # Set up tenant A
        tokens_a = register_user(client, "owner-a@approvals.com", tenant_name="Approvals Tenant A")
        header_a = _auth_header(tokens_a["access_token"])

        # Set up tenant B with an analyst
        tokens_b = register_user(client, "owner-b@approvals.com", tenant_name="Approvals Tenant B")
        header_b = _auth_header(tokens_b["access_token"])
        analyst_b_header = _create_analyst(client, header_b, "analyst-b@approvals.com")

        # Create approval in tenant A
        create_resp = client.post(f"{API}/approvals", json={"tool_name": "secret-tool"}, headers=header_a)
        assert create_resp.status_code == 201
        approval_id_a = create_resp.json()["id"]

        # Tenant B analyst should see zero approvals (their own tenant is empty)
        list_resp = client.get(f"{API}/approvals", headers=analyst_b_header)
        assert list_resp.status_code == 200
        assert list_resp.json()["total"] == 0

        # Tenant B analyst should not be able to fetch tenant A's approval by ID
        get_resp = client.get(f"{API}/approvals/{approval_id_a}", headers=analyst_b_header)
        assert get_resp.status_code == 404
