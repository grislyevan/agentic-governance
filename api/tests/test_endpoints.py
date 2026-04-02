"""Tests for endpoints router: CRUD, heartbeat, enrollment."""

from __future__ import annotations

from tests.conftest import API, _auth_header, register_user


def _auth(client):
    tokens = register_user(client, "ep@test.com", tenant_name="EP Org")
    return _auth_header(tokens["access_token"])


class TestCreateEndpoint:
    def test_create_returns_201(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/endpoints", json={"hostname": "ws-001"}, headers=headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["hostname"] == "ws-001"
        assert data["status"] == "active"
        assert "id" in data

    def test_create_with_os_info_and_management_state(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/endpoints",
            json={
                "hostname": "ws-002",
                "os_info": "macOS 15.3",
                "management_state": "managed",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        assert resp.json()["os_info"] == "macOS 15.3"
        assert resp.json()["management_state"] == "managed"

    def test_create_duplicate_returns_409(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints", json={"hostname": "dup"}, headers=headers)
        resp = client.post(
            f"{API}/endpoints", json={"hostname": "dup"}, headers=headers
        )
        assert resp.status_code == 409

    def test_create_unauthenticated_returns_401(self, client):
        resp = client.post(f"{API}/endpoints", json={"hostname": "fail"})
        assert resp.status_code == 401


class TestListEndpoints:
    def test_list_returns_all_tenant_endpoints(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints", json={"hostname": "a"}, headers=headers)
        client.post(f"{API}/endpoints", json={"hostname": "b"}, headers=headers)
        resp = client.get(f"{API}/endpoints", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2


class TestGetEndpoint:
    def test_get_returns_endpoint(self, client):
        headers = _auth(client)
        created = client.post(
            f"{API}/endpoints", json={"hostname": "fetch-me"}, headers=headers
        ).json()
        resp = client.get(f"{API}/endpoints/{created['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["hostname"] == "fetch-me"

    def test_get_nonexistent_returns_404(self, client):
        headers = _auth(client)
        resp = client.get(f"{API}/endpoints/nonexistent-id", headers=headers)
        assert resp.status_code == 404


class TestHeartbeat:
    def test_heartbeat_creates_endpoint_if_missing(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/endpoints/heartbeat",
            json={
                "hostname": "auto-reg",
                "interval_seconds": 120,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["next_expected_in"] == 120

    def test_heartbeat_updates_existing(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints", json={"hostname": "beat-me"}, headers=headers)
        resp = client.post(
            f"{API}/endpoints/heartbeat",
            json={
                "hostname": "beat-me",
                "interval_seconds": 60,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["endpoint_status"] == "active"


class TestEndpointStatus:
    def test_status_returns_computed_liveness(self, client):
        headers = _auth(client)
        client.post(
            f"{API}/endpoints/heartbeat",
            json={
                "hostname": "live-one",
                "interval_seconds": 300,
            },
            headers=headers,
        )
        resp = client.get(f"{API}/endpoints/status", headers=headers)
        assert resp.status_code == 200
        statuses = resp.json()
        assert any(s["hostname"] == "live-one" for s in statuses)


class TestEnrollment:
    def test_enroll_returns_fingerprint(self, client):
        headers = _auth(client)
        fake_pem = "-----BEGIN PUBLIC KEY-----\nMCowBQYtest\n-----END PUBLIC KEY-----"
        resp = client.post(
            f"{API}/endpoints/enroll",
            json={
                "hostname": "enrolled-ws",
                "public_key_pem": fake_pem,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "key_fingerprint" in data
        assert "endpoint_id" in data

    def test_re_enroll_replaces_key(self, client):
        headers = _auth(client)
        pem1 = "-----BEGIN PUBLIC KEY-----\nKEY1\n-----END PUBLIC KEY-----"
        pem2 = "-----BEGIN PUBLIC KEY-----\nKEY2\n-----END PUBLIC KEY-----"
        r1 = client.post(
            f"{API}/endpoints/enroll",
            json={"hostname": "rotate", "public_key_pem": pem1},
            headers=headers,
        )
        r2 = client.post(
            f"{API}/endpoints/enroll",
            json={"hostname": "rotate", "public_key_pem": pem2},
            headers=headers,
        )
        assert r1.json()["endpoint_id"] == r2.json()["endpoint_id"]
        assert r1.json()["key_fingerprint"] != r2.json()["key_fingerprint"]


class TestPerEndpointKeyRotation:
    def test_rotate_returns_new_key(self, client):
        """POST /endpoints/{id}/key/rotate returns a new plaintext agent key."""
        headers = _auth(client)
        ep = client.post(
            f"{API}/endpoints", json={"hostname": "key-rotate-test"}, headers=headers
        )
        assert ep.status_code == 201
        ep_id = ep.json()["id"]

        resp = client.post(f"{API}/endpoints/{ep_id}/key/rotate", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["endpoint_id"] == ep_id
        assert data["hostname"] == "key-rotate-test"
        assert "agent_key" in data
        assert len(data["agent_key"]) >= 32
        assert "agent_key_prefix" in data
        assert data["agent_key"].startswith(data["agent_key_prefix"])

    def test_rotate_twice_returns_different_keys(self, client):
        """Two consecutive rotations produce different keys."""
        headers = _auth(client)
        ep = client.post(
            f"{API}/endpoints", json={"hostname": "key-rotate-twice"}, headers=headers
        )
        ep_id = ep.json()["id"]

        r1 = client.post(f"{API}/endpoints/{ep_id}/key/rotate", headers=headers)
        r2 = client.post(f"{API}/endpoints/{ep_id}/key/rotate", headers=headers)
        assert r1.json()["agent_key"] != r2.json()["agent_key"]

    def test_per_endpoint_key_authenticates(self, client):
        """An agent using the per-endpoint key can ingest events."""
        headers = _auth(client)
        ep = client.post(
            f"{API}/endpoints", json={"hostname": "key-auth-test"}, headers=headers
        )
        ep_id = ep.json()["id"]

        rotate = client.post(f"{API}/endpoints/{ep_id}/key/rotate", headers=headers)
        assert rotate.status_code == 200
        new_key = rotate.json()["agent_key"]

        # Ingest an event using the per-endpoint key
        event_payload = {
            "event_id": "test-ep-key-auth-001",
            "event_type": "detection.observed",
            "event_version": "1.0",
            "observed_at": "2026-01-01T00:00:00Z",
            "endpoint": {"id": "key-auth-test"},
        }
        ingest = client.post(
            f"{API}/events",
            json=event_payload,
            headers={"X-Api-Key": new_key},
        )
        assert ingest.status_code in (201, 200), ingest.text

    def test_rotate_cross_tenant_returns_404(self, client):
        """An endpoint belonging to another tenant returns 404, not 403 (no info leak)."""
        from tests.conftest import register_user, _auth_header

        owner_a_tokens = register_user(
            client, "owner-a-rotate@test.com", tenant_name="RotateOrgA"
        )
        owner_a_headers = _auth_header(owner_a_tokens["access_token"])
        ep = client.post(
            f"{API}/endpoints",
            json={"hostname": "cross-tenant-test"},
            headers=owner_a_headers,
        )
        ep_id = ep.json()["id"]

        # Different tenant — cannot see the endpoint
        owner_b_tokens = register_user(
            client, "owner-b-rotate@test.com", tenant_name="RotateOrgB"
        )
        owner_b_headers = _auth_header(owner_b_tokens["access_token"])

        resp = client.post(
            f"{API}/endpoints/{ep_id}/key/rotate", headers=owner_b_headers
        )
        assert resp.status_code == 404

    def test_rotate_nonexistent_endpoint_returns_404(self, client):
        headers = _auth(client)
        resp = client.post(
            f"{API}/endpoints/nonexistent-id/key/rotate", headers=headers
        )
        assert resp.status_code == 404
