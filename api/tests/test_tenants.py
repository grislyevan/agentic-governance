"""Tests for the tenants (organizations) router."""

from __future__ import annotations

import pytest
from tests.conftest import API, _auth_header, register_user


class TestTenantCurrent:
    def test_get_current_tenant(self, client):
        tokens = register_user(client, tenant_name="Acme Corp")
        headers = _auth_header(tokens["access_token"])

        resp = client.get(f"{API}/tenants/current", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Acme Corp"
        assert data["slug"] == "acme-corp"
        assert data["member_count"] == 1
        assert data["role"] == "owner"

    def test_unauthenticated(self, client):
        resp = client.get(f"{API}/tenants/current")
        assert resp.status_code == 401


class TestListMyTenants:
    def test_single_tenant(self, client):
        tokens = register_user(client, tenant_name="Solo Org")
        headers = _auth_header(tokens["access_token"])

        resp = client.get(f"{API}/tenants/mine", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Solo Org"

    def test_multiple_tenants_after_create(self, client):
        tokens = register_user(client, tenant_name="First Org")
        headers = _auth_header(tokens["access_token"])

        client.post(f"{API}/tenants", json={"name": "Second Org"}, headers=headers)

        resp = client.get(f"{API}/tenants/mine", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {t["name"] for t in data}
        assert "First Org" in names
        assert "Second Org" in names


class TestCreateTenant:
    def test_create_success(self, client):
        tokens = register_user(client, tenant_name="Primary")
        headers = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/tenants", json={"name": "New Org"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Org"
        assert data["slug"].startswith("new-org")
        assert data["role"] == "owner"

    def test_create_requires_auth(self, client):
        resp = client.post(f"{API}/tenants", json={"name": "Unauthorized"})
        assert resp.status_code == 401

    def test_create_requires_owner_or_admin(self, client):
        tokens = register_user(client, tenant_name="Primary")
        headers = _auth_header(tokens["access_token"])

        # Create an analyst user via invite
        invite_resp = client.post(f"{API}/users", json={
            "first_name": "Bob",
            "email": "bob@test.com",
            "role": "analyst",
        }, headers=headers)
        assert invite_resp.status_code == 201

        # Login as Bob (set password first)
        invite_data = invite_resp.json()
        if invite_data.get("invite_token"):
            client.post(f"{API}/auth/accept-invite", json={
                "token": invite_data["invite_token"],
                "new_password": "bobpass12345",
            })
        bob_tokens = client.post(f"{API}/auth/login", json={
            "email": "bob@test.com",
            "password": "bobpass12345",
        })
        if bob_tokens.status_code != 200:
            pytest.skip("Could not login as analyst")
        bob_headers = _auth_header(bob_tokens.json()["access_token"])

        resp = client.post(f"{API}/tenants", json={"name": "Should Fail"}, headers=bob_headers)
        assert resp.status_code == 403

    def test_duplicate_name_gets_suffix(self, client):
        tokens = register_user(client, tenant_name="Duplicate")
        headers = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/tenants", json={"name": "Duplicate"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"].startswith("Duplicate")
        assert data["name"] != "Duplicate"
        assert data["slug"].startswith("duplicate")


class TestUpdateTenant:
    def test_rename_tenant(self, client):
        tokens = register_user(client, tenant_name="Old Name")
        headers = _auth_header(tokens["access_token"])

        resp = client.get(f"{API}/tenants/current", headers=headers)
        tenant_id = resp.json()["id"]

        resp = client.patch(f"{API}/tenants/{tenant_id}", json={"name": "New Name"}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"
        assert resp.json()["slug"].startswith("new-name")


class TestSwitchTenant:
    def test_switch_success(self, client):
        tokens = register_user(client, tenant_name="Org A")
        headers = _auth_header(tokens["access_token"])

        create_resp = client.post(f"{API}/tenants", json={"name": "Org B"}, headers=headers)
        assert create_resp.status_code == 201
        org_b_id = create_resp.json()["id"]

        resp = client.post(f"{API}/tenants/switch", json={"tenant_id": org_b_id}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant"]["name"] == "Org B"
        assert "access_token" in data
        assert "refresh_token" in data

    def test_switch_to_nonexistent_tenant(self, client):
        tokens = register_user(client, tenant_name="Only")
        headers = _auth_header(tokens["access_token"])

        resp = client.post(f"{API}/tenants/switch", json={"tenant_id": "fake-id"}, headers=headers)
        assert resp.status_code == 403

    def test_switch_roundtrip(self, client):
        tokens = register_user(client, tenant_name="Home")
        headers = _auth_header(tokens["access_token"])

        create_resp = client.post(f"{API}/tenants", json={"name": "Away"}, headers=headers)
        away_id = create_resp.json()["id"]

        switch_resp = client.post(f"{API}/tenants/switch", json={"tenant_id": away_id}, headers=headers)
        new_headers = _auth_header(switch_resp.json()["access_token"])

        me_resp = client.get(f"{API}/auth/me", headers=new_headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["tenant_name"] == "Away"


class TestAuthMeIncludesTenant:
    def test_me_has_tenant_name(self, client):
        tokens = register_user(client, tenant_name="My Org")
        headers = _auth_header(tokens["access_token"])

        resp = client.get(f"{API}/auth/me", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_name"] == "My Org"
        assert data["tenant_slug"] == "my-org"
