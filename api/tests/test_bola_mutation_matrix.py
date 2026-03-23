"""BOLA mutation-route matrix tests for tenant isolation across roles.

Verifies that cross-tenant mutation attempts are blocked for owner/admin/analyst
where applicable across high-risk write/delete endpoints.
"""

from __future__ import annotations

import uuid

import pytest
from tests.conftest import API, _auth_header, register_user


ROLES = ("owner", "admin", "analyst")


def _setup_two_tenants(client):
    suffix = uuid.uuid4().hex[:8]
    a = register_user(client, f"owner-a-{suffix}@test.com", tenant_name=f"A-{suffix}")
    b = register_user(client, f"owner-b-{suffix}@test.com", tenant_name=f"B-{suffix}")
    return _auth_header(a["access_token"]), _auth_header(b["access_token"])


def _create_user_with_role(client, owner_headers, role: str):
    suffix = uuid.uuid4().hex[:8]
    email = f"{role}-{suffix}@test.com"
    password = "testpass12345"
    resp = client.post(
        f"{API}/users",
        json={
            "email": email,
            "password": password,
            "first_name": role.title(),
            "last_name": "Matrix",
            "role": role,
        },
        headers=owner_headers,
    )
    assert resp.status_code == 201, resp.text
    login = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return _auth_header(login.json()["access_token"])


def _actor_header(client, owner_a, role: str):
    if role == "owner":
        return owner_a
    return _create_user_with_role(client, owner_a, role)


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_endpoint_patch_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)
    ep = client.post(f"{API}/endpoints", json={"hostname": f"ep-{uuid.uuid4().hex[:6]}"}, headers=owner_b)
    endpoint_id = ep.json()["id"]

    resp = client.patch(
        f"{API}/endpoints/{endpoint_id}",
        json={"management_state": "managed"},
        headers=actor,
    )
    assert resp.status_code in ((404,) if role in ("owner", "admin") else (403,))


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_enforcement_posture_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)
    ep = client.post(f"{API}/endpoints", json={"hostname": f"enf-{uuid.uuid4().hex[:6]}"}, headers=owner_b)
    endpoint_id = ep.json()["id"]

    resp = client.put(
        f"{API}/enforcement/endpoints/{endpoint_id}/posture",
        json={"enforcement_posture": "audit"},
        headers=actor,
    )
    assert resp.status_code in ((404,) if role in ("owner", "admin") else (403,))


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_policy_mutations_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)
    pol = client.post(
        f"{API}/policies",
        json={"rule_id": f"B-{uuid.uuid4().hex[:6]}", "description": "tenant b"},
        headers=owner_b,
    )
    policy_id = pol.json()["id"]

    patch_resp = client.patch(
        f"{API}/policies/{policy_id}",
        json={"description": "malicious update"},
        headers=actor,
    )
    del_resp = client.delete(f"{API}/policies/{policy_id}", headers=actor)

    expected = (404,) if role in ("owner", "admin") else (403,)
    assert patch_resp.status_code in expected
    assert del_resp.status_code in expected


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_user_mutations_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)
    created = client.post(
        f"{API}/users",
        json={
            "email": f"victim-{uuid.uuid4().hex[:8]}@test.com",
            "password": "testpass12345",
            "first_name": "Victim",
            "last_name": "User",
            "role": "analyst",
        },
        headers=owner_b,
    )
    target_user_id = created.json()["id"]

    patch_resp = client.patch(
        f"{API}/users/{target_user_id}",
        json={"first_name": "Pwned"},
        headers=actor,
    )
    del_resp = client.delete(f"{API}/users/{target_user_id}", headers=actor)

    if role == "owner":
        assert patch_resp.status_code == 404
        assert del_resp.status_code == 404
    elif role == "admin":
        assert patch_resp.status_code == 404
        assert del_resp.status_code == 403
    else:
        assert patch_resp.status_code == 403
        assert del_resp.status_code == 403


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_webhook_mutations_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)
    created = client.post(
        f"{API}/webhooks",
        json={"url": "https://example.com/hook", "events": []},
        headers=owner_b,
    )
    webhook_id = created.json()["id"]

    patch_resp = client.patch(
        f"{API}/webhooks/{webhook_id}",
        json={"is_active": False},
        headers=actor,
    )
    del_resp = client.delete(f"{API}/webhooks/{webhook_id}", headers=actor)

    expected = (404,) if role in ("owner", "admin") else (403,)
    assert patch_resp.status_code in expected
    assert del_resp.status_code in expected


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_tenant_update_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)

    current_b = client.get(f"{API}/tenants/current", headers=owner_b)
    tenant_b_id = current_b.json()["id"]

    resp = client.patch(
        f"{API}/tenants/{tenant_b_id}",
        json={"name": "stolen-tenant"},
        headers=actor,
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_profile_mutations_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)

    created = client.post(
        f"{API}/endpoint-profiles",
        json={"name": f"B profile {uuid.uuid4().hex[:6]}"},
        headers=owner_b,
    )
    profile_id = created.json()["id"]

    patch_resp = client.patch(
        f"{API}/endpoint-profiles/{profile_id}",
        json={"name": "hijacked"},
        headers=actor,
    )
    del_resp = client.delete(f"{API}/endpoint-profiles/{profile_id}", headers=actor)

    expected = (404,) if role in ("owner", "admin") else (403,)
    assert patch_resp.status_code in expected
    assert del_resp.status_code in expected


@pytest.mark.parametrize("role", ROLES)
def test_cross_tenant_event_block_mutation_blocked(client, role):
    owner_a, owner_b = _setup_two_tenants(client)
    actor = _actor_header(client, owner_a, role)

    evt = client.post(
        f"{API}/events",
        json={
            "event_id": f"evt-{uuid.uuid4().hex[:6]}",
            "event_type": "detection",
            "event_version": "1.0",
            "observed_at": "2026-01-01T00:00:00Z",
            "tool": {"name": "Cursor"},
        },
        headers=owner_b,
    )
    event_id = evt.json()["id"]

    resp = client.post(f"{API}/events/{event_id}/block", headers=actor)
    if role in ("owner", "admin"):
        assert resp.status_code == 404
    else:
        assert resp.status_code == 403
