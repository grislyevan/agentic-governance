"""Tests for compute_status() on the Endpoint model, including tamper_suspected logic."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone as tz
from unittest.mock import MagicMock

from models.endpoint import (
    ENDPOINT_STATUS_ACTIVE,
    ENDPOINT_STATUS_STALE,
    ENDPOINT_STATUS_TAMPER_SUSPECTED,
    ENDPOINT_STATUS_UNGOVERNED,
    Endpoint,
)


def _make_endpoint(
    *,
    elapsed_seconds: float,
    heartbeat_interval: int,
    management_state: str = "unmanaged",
    status: str = "active",
) -> MagicMock:
    """Return a MagicMock that mimics an Endpoint with compute_status() bound."""
    ep = MagicMock(spec=Endpoint)
    ep.status = status
    ep.heartbeat_interval = heartbeat_interval
    ep.management_state = management_state
    ep.last_seen_at = datetime.now(tz.utc) - timedelta(seconds=elapsed_seconds)

    # Bind the real unbound method so the mock behaves like an actual instance.
    ep.compute_status = lambda: Endpoint.compute_status(ep)
    return ep


class TestComputeStatus(unittest.TestCase):
    def test_active_endpoint(self):
        """100s elapsed, 300s interval → active (threshold = 450s)."""
        ep = _make_endpoint(elapsed_seconds=100, heartbeat_interval=300)
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_ACTIVE)

    def test_stale_endpoint(self):
        """600s elapsed, 300s interval → stale (threshold = 450s, stale ceiling = 1350s)."""
        ep = _make_endpoint(elapsed_seconds=600, heartbeat_interval=300)
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_STALE)

    def test_tamper_suspected_endpoint(self):
        """1500s elapsed, 300s interval, managed → tamper_suspected (elapsed > 1350s)."""
        ep = _make_endpoint(
            elapsed_seconds=1500,
            heartbeat_interval=300,
            management_state="managed",
        )
        self.assertEqual(ep.compute_status(), ENDPOINT_STATUS_TAMPER_SUSPECTED)

    def test_unmanaged_endpoint_not_tamper_suspected(self):
        """1500s elapsed, 300s interval, unmanaged → ungoverned, NOT tamper_suspected."""
        ep = _make_endpoint(
            elapsed_seconds=1500,
            heartbeat_interval=300,
            management_state="unmanaged",
        )
        result = ep.compute_status()
        self.assertNotEqual(result, ENDPOINT_STATUS_TAMPER_SUSPECTED)
        self.assertEqual(result, ENDPOINT_STATUS_UNGOVERNED)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# Integration tests for uninstall token and decommission endpoints
# ---------------------------------------------------------------------------

import pytest
from tests.conftest import API, _auth_header, register_user


def _setup(client):
    """Register a user/tenant and create an endpoint; return (headers, endpoint_id)."""
    tokens = register_user(client, "decom@test.com", tenant_name="Decom Org")
    headers = _auth_header(tokens["access_token"])
    resp = client.post(f"{API}/endpoints", json={"hostname": "ws-decom"}, headers=headers)
    assert resp.status_code == 201
    endpoint_id = resp.json()["id"]
    return headers, endpoint_id


class TestGenerateUninstallToken:
    def test_generate_uninstall_token(self, client):
        """POST uninstall-token returns 200 with a 64-char hex token."""
        headers, endpoint_id = _setup(client)
        resp = client.post(f"{API}/endpoints/{endpoint_id}/uninstall-token", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "uninstall_token" in data
        token = data["uninstall_token"]
        assert len(token) == 64
        # Must be hex characters only
        int(token, 16)


class TestDecommissionEndpoint:
    def test_decommission_endpoint(self, client):
        """POST decommission sets status to decommissioned."""
        headers, endpoint_id = _setup(client)
        resp = client.post(f"{API}/endpoints/{endpoint_id}/decommission", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "decommissioned"
        assert data["id"] == endpoint_id


class TestValidateUninstallToken:
    def test_validate_uninstall_token_correct(self, client):
        """Validate with the correct token returns valid=true."""
        headers, endpoint_id = _setup(client)
        gen_resp = client.post(f"{API}/endpoints/{endpoint_id}/uninstall-token", headers=headers)
        assert gen_resp.status_code == 200
        token = gen_resp.json()["uninstall_token"]

        val_resp = client.post(
            f"{API}/endpoints/{endpoint_id}/validate-uninstall-token",
            json={"token": token},
            headers=headers,
        )
        assert val_resp.status_code == 200
        assert val_resp.json()["valid"] is True

    def test_validate_uninstall_token_wrong(self, client):
        """Validate with a wrong token returns valid=false."""
        headers, endpoint_id = _setup(client)
        client.post(f"{API}/endpoints/{endpoint_id}/uninstall-token", headers=headers)

        val_resp = client.post(
            f"{API}/endpoints/{endpoint_id}/validate-uninstall-token",
            json={"token": "a" * 64},
            headers=headers,
        )
        assert val_resp.status_code == 200
        assert val_resp.json()["valid"] is False


class TestDecommissionRequiresAdmin:
    def test_decommission_requires_admin(self, client):
        """An analyst role should receive 403 when attempting to decommission."""
        import uuid as _uuid
        import core.database as _db_mod
        from core.auth import create_access_token
        from models.user import User
        from models.tenant import Tenant

        # Create owner and endpoint
        owner_tokens = register_user(client, "owner@test.com", tenant_name="Admin Org")
        owner_headers = _auth_header(owner_tokens["access_token"])
        ep_resp = client.post(f"{API}/endpoints", json={"hostname": "ws-perm"}, headers=owner_headers)
        assert ep_resp.status_code == 201
        endpoint_id = ep_resp.json()["id"]

        # Register a second user (analyst) and downgrade their role in the DB,
        # then issue a JWT scoped to the owner's tenant so strict_tenant_filter passes.
        register_user(client, "analyst@test.com")

        with _db_mod.SessionLocal() as db:
            analyst_user = db.query(User).filter(User.email == "analyst@test.com").first()
            owner_tenant = db.query(Tenant).filter(Tenant.name == "Admin Org").first()
            # Downgrade role to analyst so require_role("owner","admin") fires.
            analyst_user.role = "analyst"
            db.commit()
            analyst_id = analyst_user.id
            owner_tenant_id = owner_tenant.id

        # Issue a JWT scoped to the owner's tenant (so strict_tenant_filter passes).
        analyst_token = create_access_token(
            subject=analyst_id,
            tenant_id=owner_tenant_id,
        )
        analyst_headers = _auth_header(analyst_token)
        resp = client.post(f"{API}/endpoints/{endpoint_id}/decommission", headers=analyst_headers)
        assert resp.status_code == 403
