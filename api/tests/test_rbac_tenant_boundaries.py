"""RBAC and tenant boundary: owner, admin, analyst, viewer access matrix.

Complements test_tenant_isolation.py with explicit admin/viewer coverage
and governance sign-off requirements (docs/governance-tenant-scoping.md).
"""

from __future__ import annotations

from tests.conftest import API, _auth_header, register_user


def _setup_two_tenants(client):
    tokens_a = register_user(client, "alice-rbac@a.com", tenant_name="Tenant A")
    tokens_b = register_user(client, "bob-rbac@b.com", tenant_name="Tenant B")
    return (
        _auth_header(tokens_a["access_token"]),
        _auth_header(tokens_b["access_token"]),
    )


def _create_user_with_role(client, owner_headers, email, role, password="testpass12345"):
    """Create a user with the given role via owner API; return auth header."""
    client.post(
        f"{API}/users",
        json={
            "email": email,
            "password": password,
            "first_name": "Test",
            "last_name": role.capitalize(),
            "role": role,
        },
        headers=owner_headers,
    )
    resp = client.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return _auth_header(resp.json()["access_token"])


class TestAdminCrossTenantRead:
    """Admin has same read-only cross-tenant visibility as owner."""

    def test_admin_sees_all_tenant_endpoints(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        admin_a = _create_user_with_role(client, auth_a, "admin-rbac@a.com", "admin")

        client.post(f"{API}/endpoints", json={"hostname": "ws-a"}, headers=auth_a)
        client.post(f"{API}/endpoints", json={"hostname": "ws-b"}, headers=auth_b)

        resp = client.get(f"{API}/endpoints", headers=admin_a)
        assert resp.status_code == 200
        names = [e["hostname"] for e in resp.json()["items"]]
        assert "ws-a" in names
        assert "ws-b" in names

    def test_admin_sees_all_tenant_policies(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        admin_a = _create_user_with_role(client, auth_a, "admin-pol@a.com", "admin")

        client.post(
            f"{API}/policies",
            json={"rule_id": "RULE-A", "description": "A"},
            headers=auth_a,
        )
        client.post(
            f"{API}/policies",
            json={"rule_id": "RULE-B", "description": "B"},
            headers=auth_b,
        )

        resp = client.get(f"{API}/policies", headers=admin_a)
        assert resp.status_code == 200
        rules = [p["rule_id"] for p in resp.json()["items"]]
        assert "RULE-A" in rules
        assert "RULE-B" in rules


class TestViewerTenantIsolation:
    """Viewer is scoped to own tenant only (read-only; no cross-tenant)."""

    def test_viewer_sees_only_own_tenant_endpoints(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        viewer_a = _create_user_with_role(client, auth_a, "viewer-rbac@a.com", "viewer")

        client.post(f"{API}/endpoints", json={"hostname": "ws-a"}, headers=auth_a)
        client.post(f"{API}/endpoints", json={"hostname": "ws-b"}, headers=auth_b)

        resp = client.get(f"{API}/endpoints", headers=viewer_a)
        assert resp.status_code == 200
        names = [e["hostname"] for e in resp.json()["items"]]
        assert "ws-a" in names
        assert "ws-b" not in names

    def test_viewer_cannot_get_other_tenant_endpoint_by_id(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        viewer_a = _create_user_with_role(client, auth_a, "viewer-id@a.com", "viewer")

        resp = client.post(
            f"{API}/endpoints",
            json={"hostname": "private-b"},
            headers=auth_b,
        )
        ep_id = resp.json()["id"]

        resp = client.get(f"{API}/endpoints/{ep_id}", headers=viewer_a)
        assert resp.status_code == 404


class TestAnalystCannotMutateOtherTenant:
    """Analyst cannot create/update/delete policies; cannot delete other tenant resources."""

    def test_analyst_cannot_create_policy(self, client):
        auth_a, _ = _setup_two_tenants(client)
        analyst_a = _create_user_with_role(client, auth_a, "analyst-mut@a.com", "analyst")

        resp = client.post(
            f"{API}/policies",
            json={"rule_id": "CROSS-TENANT", "description": "Forbidden"},
            headers=analyst_a,
        )
        assert resp.status_code == 403

    def test_analyst_cannot_delete_other_tenant_webhook(self, client):
        auth_a, auth_b = _setup_two_tenants(client)
        analyst_a = _create_user_with_role(client, auth_a, "analyst-del@a.com", "analyst")

        wh = client.post(
            f"{API}/webhooks",
            json={"url": "https://b.com/cb", "events": ["detection"]},
            headers=auth_b,
        )
        assert wh.status_code == 201
        wh_id = wh.json()["id"]

        resp = client.delete(f"{API}/webhooks/{wh_id}", headers=analyst_a)
        assert resp.status_code in (403, 404)


class TestViewerCannotMutate:
    """Viewer has read-only access; mutations are forbidden."""

    def test_viewer_cannot_create_policy(self, client):
        auth_a, _ = _setup_two_tenants(client)
        viewer_a = _create_user_with_role(client, auth_a, "viewer-create@a.com", "viewer")

        resp = client.post(
            f"{API}/policies",
            json={"rule_id": "VIEWER-RULE", "description": "Should fail"},
            headers=viewer_a,
        )
        assert resp.status_code == 403

    def test_viewer_cannot_read_audit_log(self, client):
        auth_a, _ = _setup_two_tenants(client)
        viewer_a = _create_user_with_role(client, auth_a, "viewer-audit@a.com", "viewer")

        resp = client.get(f"{API}/audit-log", headers=viewer_a)
        assert resp.status_code == 403


class TestAuditLogListSuccess:
    """Owner, admin, and analyst can list audit log and get 200 with valid response shape."""

    def test_owner_can_list_audit_log(self, client):
        auth_a, _ = _setup_two_tenants(client)
        resp = client.get(f"{API}/audit-log", headers=auth_a)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data and "page" in data and "page_size" in data and "items" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            assert "id" in item and "action" in item and "occurred_at" in item

    def test_admin_can_list_audit_log(self, client):
        auth_a, _ = _setup_two_tenants(client)
        admin_a = _create_user_with_role(client, auth_a, "admin-audit-list@a.com", "admin")
        resp = client.get(f"{API}/audit-log", headers=admin_a)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data and "items" in data

    def test_analyst_can_list_audit_log(self, client):
        auth_a, _ = _setup_two_tenants(client)
        analyst_a = _create_user_with_role(client, auth_a, "analyst-audit-list@a.com", "analyst")
        resp = client.get(f"{API}/audit-log", headers=analyst_a)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data and "items" in data
