"""Tests for PATCH /enforcement/allow-list/:id."""

from tests.conftest import API, _auth_header, register_user


def _register_admin(client, email="patch-admin@test.com", tenant="PatchOrg"):
    tokens = register_user(client, email, tenant_name=tenant)
    return _auth_header(tokens["access_token"]), tokens


def _create_entry(client, headers, pattern="cursor.exe"):
    from datetime import datetime, timezone, timedelta
    expires = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    resp = client.post(f"{API}/enforcement/allow-list", headers=headers, json={
        "pattern": pattern,
        "pattern_type": "process_name",
        "reason_code": "known_safe",
        "expires_at": expires,
    })
    assert resp.status_code == 201
    return resp.json()


class TestAllowListPatch:
    def test_patch_reason_code(self, client):
        headers, _ = _register_admin(client)
        entry = _create_entry(client, headers)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"reason_code": "updated_reason"},
        )
        assert resp.status_code == 200
        assert resp.json()["reason_code"] == "updated_reason"

    def test_patch_scope(self, client):
        headers, _ = _register_admin(client, email="patch2@test.com", tenant="PatchOrg2")
        entry = _create_entry(client, headers)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"scope": "endpoint"},
        )
        assert resp.status_code == 200
        assert resp.json()["scope"] == "endpoint"

    def test_patch_requires_admin(self, client):
        from core.database import get_db
        from models.user import User
        admin_h, _ = _register_admin(client, email="patch-admin3@test.com", tenant="PatchOrg3")
        viewer_tokens = register_user(client, "patch-viewer@test.com", tenant_name="PatchOrg3v")
        viewer_h = _auth_header(viewer_tokens["access_token"])
        db = next(get_db())
        u = db.query(User).filter(User.email == "patch-viewer@test.com").first()
        u.role = "viewer"
        db.commit()
        entry = _create_entry(client, admin_h)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=viewer_h,
            json={"reason_code": "bad"},
        )
        assert resp.status_code == 403

    def test_patch_cross_tenant_denied(self, client):
        headers_a, _ = _register_admin(client, email="patch-a@test.com", tenant="OrgA")
        headers_b, _ = _register_admin(client, email="patch-b@test.com", tenant="OrgB")
        entry = _create_entry(client, headers_a)
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers_b,
            json={"reason_code": "steal"},
        )
        assert resp.status_code == 404  # strict_tenant_filter → not found

    def test_patch_immutable_fields_ignored(self, client):
        headers, _ = _register_admin(client, email="patch-imm@test.com", tenant="ImmOrg")
        entry = _create_entry(client, headers)
        original_id = entry["id"]
        original_tenant = entry["tenant_id"]
        resp = client.patch(
            f"{API}/enforcement/allow-list/{entry['id']}",
            headers=headers,
            json={"id": "hacked", "tenant_id": "hacked", "reason_code": "safe"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == original_id
        assert data["tenant_id"] == original_tenant
        assert data["reason_code"] == "safe"

    def test_patch_nonexistent_returns_404(self, client):
        headers, _ = _register_admin(client, email="patch-404@test.com", tenant="Org404")
        resp = client.patch(
            f"{API}/enforcement/allow-list/nonexistent-id",
            headers=headers,
            json={"reason_code": "x"},
        )
        assert resp.status_code == 404
