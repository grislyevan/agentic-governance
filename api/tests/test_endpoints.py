"""Tests for endpoints router: CRUD, heartbeat, enrollment."""

from __future__ import annotations

from tests.conftest import API, _auth_header, register_user


def _auth(client):
    tokens = register_user(client, "ep@test.com", tenant_name="EP Org")
    return _auth_header(tokens["access_token"])


class TestCreateEndpoint:
    def test_create_returns_201(self, client):
        headers = _auth(client)
        resp = client.post(f"{API}/endpoints", json={"hostname": "ws-001"}, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["hostname"] == "ws-001"
        assert data["status"] == "active"
        assert "id" in data

    def test_create_with_os_info_and_posture(self, client):
        headers = _auth(client)
        resp = client.post(f"{API}/endpoints", json={
            "hostname": "ws-002",
            "os_info": "macOS 15.3",
            "posture": "managed",
        }, headers=headers)
        assert resp.status_code == 201
        assert resp.json()["os_info"] == "macOS 15.3"
        assert resp.json()["posture"] == "managed"

    def test_create_duplicate_returns_409(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints", json={"hostname": "dup"}, headers=headers)
        resp = client.post(f"{API}/endpoints", json={"hostname": "dup"}, headers=headers)
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
        created = client.post(f"{API}/endpoints", json={"hostname": "fetch-me"}, headers=headers).json()
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
        resp = client.post(f"{API}/endpoints/heartbeat", json={
            "hostname": "auto-reg",
            "interval_seconds": 120,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["next_expected_in"] == 120

    def test_heartbeat_updates_existing(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints", json={"hostname": "beat-me"}, headers=headers)
        resp = client.post(f"{API}/endpoints/heartbeat", json={
            "hostname": "beat-me",
            "interval_seconds": 60,
        }, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["endpoint_status"] == "active"


class TestEndpointStatus:
    def test_status_returns_computed_liveness(self, client):
        headers = _auth(client)
        client.post(f"{API}/endpoints/heartbeat", json={
            "hostname": "live-one",
            "interval_seconds": 300,
        }, headers=headers)
        resp = client.get(f"{API}/endpoints/status", headers=headers)
        assert resp.status_code == 200
        statuses = resp.json()
        assert any(s["hostname"] == "live-one" for s in statuses)


class TestEnrollment:
    def test_enroll_returns_fingerprint(self, client):
        headers = _auth(client)
        fake_pem = "-----BEGIN PUBLIC KEY-----\nMCowBQYtest\n-----END PUBLIC KEY-----"
        resp = client.post(f"{API}/endpoints/enroll", json={
            "hostname": "enrolled-ws",
            "public_key_pem": fake_pem,
        }, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "key_fingerprint" in data
        assert "endpoint_id" in data

    def test_re_enroll_replaces_key(self, client):
        headers = _auth(client)
        pem1 = "-----BEGIN PUBLIC KEY-----\nKEY1\n-----END PUBLIC KEY-----"
        pem2 = "-----BEGIN PUBLIC KEY-----\nKEY2\n-----END PUBLIC KEY-----"
        r1 = client.post(f"{API}/endpoints/enroll", json={"hostname": "rotate", "public_key_pem": pem1}, headers=headers)
        r2 = client.post(f"{API}/endpoints/enroll", json={"hostname": "rotate", "public_key_pem": pem2}, headers=headers)
        assert r1.json()["endpoint_id"] == r2.json()["endpoint_id"]
        assert r1.json()["key_fingerprint"] != r2.json()["key_fingerprint"]
