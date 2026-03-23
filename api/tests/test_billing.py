"""Tests for the billing endpoints and tier limits."""

from __future__ import annotations

import pytest

from core.config import settings
from core.tier_limits import (
    TIER_LIMITS,
    check_endpoint_limit,
    check_event_limit,
    check_feature,
    check_user_limit,
    get_limits,
)
from tests.conftest import API, _auth_header, login_user, register_user


def _setup_owner(client):
    register_user(client, email="owner@billing.com", password="billingpass123", tenant_name="BillTenant")
    tokens = login_user(client, email="owner@billing.com", password="billingpass123")
    return _auth_header(tokens["access_token"])


# ── Tier limits unit tests ────────────────────────────────────────────


class TestTierLimits:
    def test_free_limits(self):
        limits = get_limits("free")
        assert limits.max_endpoints == 3
        assert limits.max_events_per_day == 1000
        assert limits.max_users == 1
        assert limits.webhook_enabled is False
        assert limits.sso_enabled is False
        assert limits.retention_days == 7

    def test_pro_limits(self):
        limits = get_limits("pro")
        assert limits.max_endpoints == 25
        assert limits.max_events_per_day is None
        assert limits.max_users == 10
        assert limits.webhook_enabled is True
        assert limits.sso_enabled is False
        assert limits.retention_days == 90

    def test_enterprise_limits(self):
        limits = get_limits("enterprise")
        assert limits.max_endpoints is None
        assert limits.max_events_per_day is None
        assert limits.max_users is None
        assert limits.webhook_enabled is True
        assert limits.sso_enabled is True
        assert limits.siem_export is True
        assert limits.retention_days == 365

    def test_unknown_tier_falls_back_to_free(self):
        limits = get_limits("unknown")
        assert limits == TIER_LIMITS["free"]

    def test_endpoint_limit_free_allows_under(self):
        ok, reason = check_endpoint_limit("free", 2)
        assert ok is True
        assert reason is None

    def test_endpoint_limit_free_blocks_at_max(self):
        ok, reason = check_endpoint_limit("free", 3)
        assert ok is False
        assert "3" in reason

    def test_endpoint_limit_enterprise_unlimited(self):
        ok, reason = check_endpoint_limit("enterprise", 9999)
        assert ok is True

    def test_event_limit_free_blocks_at_max(self):
        ok, reason = check_event_limit("free", 1000)
        assert ok is False
        assert "1000" in reason

    def test_event_limit_pro_unlimited(self):
        ok, reason = check_event_limit("pro", 999999)
        assert ok is True

    def test_user_limit_free(self):
        ok, reason = check_user_limit("free", 1)
        assert ok is False

    def test_user_limit_pro_allows(self):
        ok, reason = check_user_limit("pro", 5)
        assert ok is True

    def test_feature_check_webhooks_free(self):
        ok, reason = check_feature("free", "webhooks")
        assert ok is False

    def test_feature_check_webhooks_pro(self):
        ok, reason = check_feature("pro", "webhooks")
        assert ok is True

    def test_feature_check_sso_enterprise(self):
        ok, reason = check_feature("enterprise", "sso")
        assert ok is True


# ── Billing API tests ─────────────────────────────────────────────────


class TestBillingStatus:
    def test_billing_status_returns_free(self, client):
        headers = _setup_owner(client)
        resp = client.get(f"{API}/billing/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["status"] == "active"
        assert data["stripe_configured"] is False
        assert "limits" in data
        assert data["limits"]["max_endpoints"] == 3

    def test_billing_status_requires_auth(self, client):
        resp = client.get(f"{API}/billing/status")
        assert resp.status_code in (401, 403)


class TestBillingTiers:
    def test_tiers_returns_all_plans(self, client):
        headers = _setup_owner(client)
        resp = client.get(f"{API}/billing/tiers", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "free" in data
        assert "pro" in data
        assert "enterprise" in data
        assert data["free"]["max_endpoints"] == 3
        assert data["pro"]["max_endpoints"] == 25
        assert data["enterprise"]["max_endpoints"] is None


class TestBillingCheckout:
    def test_checkout_requires_stripe(self, client):
        """Without Stripe configured, checkout returns 503."""
        headers = _setup_owner(client)
        resp = client.post(
            f"{API}/billing/checkout",
            json={"tier": "pro", "success_url": "http://x/ok", "cancel_url": "http://x/no"},
            headers=headers,
        )
        assert resp.status_code == 503

    def test_checkout_rejects_free_tier(self, client):
        headers = _setup_owner(client)
        original = settings.stripe_secret_key
        settings.stripe_secret_key = "sk_test_fake"
        settings.stripe_webhook_secret = "whsec_fake"
        try:
            resp = client.post(
                f"{API}/billing/checkout",
                json={"tier": "free", "success_url": "http://x/ok", "cancel_url": "http://x/no"},
                headers=headers,
            )
            assert resp.status_code == 400
        finally:
            settings.stripe_secret_key = original
            settings.stripe_webhook_secret = ""

    def test_checkout_requires_owner_or_admin(self, client):
        """A viewer should not be able to initiate checkout."""
        headers = _setup_owner(client)
        viewer_resp = client.post(
            f"{API}/users",
            json={"email": "viewer@billing.com", "role": "viewer"},
            headers=headers,
        )
        if viewer_resp.status_code == 201:
            viewer_data = viewer_resp.json()
            if "invite_token" in viewer_data:
                client.post(
                    f"{API}/auth/accept-invite",
                    json={"token": viewer_data["invite_token"], "password": "viewerpass123"},
                )
                viewer_tokens = login_user(client, email="viewer@billing.com", password="viewerpass123")
                viewer_headers = _auth_header(viewer_tokens["access_token"])
                resp = client.post(
                    f"{API}/billing/checkout",
                    json={"tier": "pro", "success_url": "http://x/ok", "cancel_url": "http://x/no"},
                    headers=viewer_headers,
                )
                assert resp.status_code == 403


class TestBillingPortal:
    def test_portal_requires_stripe(self, client):
        headers = _setup_owner(client)
        resp = client.post(
            f"{API}/billing/portal",
            json={"return_url": "http://x/return"},
            headers=headers,
        )
        assert resp.status_code == 503


class TestBillingWebhook:
    def test_webhook_requires_stripe(self, client):
        resp = client.post(f"{API}/billing/webhook", content=b'{}')
        assert resp.status_code == 503

    def test_webhook_requires_signature(self, client):
        original = settings.stripe_secret_key
        settings.stripe_secret_key = "sk_test_fake"
        settings.stripe_webhook_secret = "whsec_fake"
        try:
            resp = client.post(f"{API}/billing/webhook", content=b'{}')
            assert resp.status_code == 400
        finally:
            settings.stripe_secret_key = original
            settings.stripe_webhook_secret = ""
