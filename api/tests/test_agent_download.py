"""Tests for the agent download router (tenant agent key, JWT auth, email enrollment)."""

from __future__ import annotations

import json
import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.conftest import API, _auth_header, register_user


def _register_owner(client):
    """Register an owner and return (auth_header_dict, tokens_dict)."""
    tokens = register_user(client, "dl-owner@test.com", tenant_name="DL Org")
    return _auth_header(tokens["access_token"]), tokens


def _register_viewer(client):
    """Register a viewer-role user for role restriction tests."""
    from core.database import get_db
    from models.user import User

    tokens = register_user(client, "dl-viewer@test.com", tenant_name="Viewer Org")
    db = next(get_db())
    user = db.query(User).filter(User.email == "dl-viewer@test.com").first()
    user.role = "viewer"
    db.commit()
    return _auth_header(tokens["access_token"]), tokens


def _create_fake_package(tmp_path: Path, name: str) -> Path:
    pkg_dir = tmp_path / "dist" / "packages"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / name).write_bytes(b"fake-installer-content")
    return pkg_dir


class TestAgentDownloadAuth:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get(f"{API}/agent/download?platform=macos")
        assert resp.status_code == 401

    def test_viewer_role_returns_403(self, client):
        headers, _ = _register_viewer(client)
        resp = client.get(f"{API}/agent/download?platform=macos", headers=headers)
        assert resp.status_code == 403

    def test_jwt_auth_works(self, client, tmp_path):
        """JWT-only auth succeeds (no X-Api-Key needed)."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, _ = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(f"{API}/agent/download?platform=macos", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"


class TestAgentDownloadMissingPackage:
    def test_missing_package_returns_404(self, client):
        headers, _ = _register_owner(client)
        resp = client.get(f"{API}/agent/download?platform=linux", headers=headers)
        assert resp.status_code == 404
        assert "pre-built" in resp.json()["detail"].lower()


class TestAgentDownloadTenantKey:
    def test_zip_contains_tenant_agent_key(self, client, tmp_path):
        """The downloaded zip embeds the tenant's agent key, not a user API key."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, tokens = _register_owner(client)

        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(f"{API}/agent/download?platform=macos", headers=headers)

        assert resp.status_code == 200
        zf = zipfile.ZipFile(BytesIO(resp.content))
        names = zf.namelist()
        assert "agent.env" in names
        assert "collector.json" in names
        assert "README.md" in names

        env_content = zf.read("agent.env").decode()
        assert "AGENTIC_GOV_API_KEY=" in env_content
        # The key should NOT be the user's API key
        assert tokens["api_key"] not in env_content

        cfg = json.loads(zf.read("collector.json"))
        assert "api_key" in cfg
        assert cfg["api_key"] != tokens["api_key"]
        assert len(cfg["api_key"]) == 64

    def test_tenant_key_is_auto_generated(self, client, tmp_path):
        """Downloading auto-generates a tenant key if one doesn't exist."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, _ = _register_owner(client)

        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp1 = client.get(f"{API}/agent/download?platform=macos", headers=headers)
            resp2 = client.get(f"{API}/agent/download?platform=macos", headers=headers)

        zf1 = zipfile.ZipFile(BytesIO(resp1.content))
        zf2 = zipfile.ZipFile(BytesIO(resp2.content))
        cfg1 = json.loads(zf1.read("collector.json"))
        cfg2 = json.loads(zf2.read("collector.json"))
        assert cfg1["api_key"] == cfg2["api_key"]

    def test_agent_can_auth_with_tenant_key(self, client, tmp_path):
        """An agent using the tenant key can call the heartbeat endpoint."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, _ = _register_owner(client)

        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(f"{API}/agent/download?platform=macos", headers=headers)

        cfg = json.loads(zipfile.ZipFile(BytesIO(resp.content)).read("collector.json"))
        agent_key = cfg["api_key"]

        resp = client.post(
            f"{API}/endpoints/heartbeat",
            json={"hostname": "test-agent-host"},
            headers={"X-Api-Key": agent_key},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAgentDownloadPlatforms:
    def test_download_windows(self, client, tmp_path):
        pkg_dir = _create_fake_package(tmp_path, "detec-agent.zip")
        headers, _ = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(
                f"{API}/agent/download?platform=windows&interval=600&protocol=tcp",
                headers=headers,
            )
        assert resp.status_code == 200
        cfg = json.loads(zipfile.ZipFile(BytesIO(resp.content)).read("collector.json"))
        assert cfg["interval"] == 600
        assert cfg["protocol"] == "tcp"
        assert "gateway_port" in cfg

    def test_download_linux(self, client, tmp_path):
        pkg_dir = _create_fake_package(tmp_path, "detec-agent-linux.tar.gz")
        headers, _ = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(f"{API}/agent/download?platform=linux", headers=headers)
        assert resp.status_code == 200
        assert "detec-agent-linux.tar.gz" in zipfile.ZipFile(BytesIO(resp.content)).namelist()


class TestTokenDownload:
    def test_token_download_works(self, client, tmp_path):
        """Token-based download works without authentication."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, tokens = _register_owner(client)

        from core.database import get_db
        from models.auth_token import AuthToken
        from models.user import User

        db = next(get_db())
        user = db.query(User).filter(User.email == "dl-owner@test.com").first()
        token_obj, raw_token = AuthToken.create_download_token(user.id)
        db.add(token_obj)
        db.commit()

        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(f"{API}/agent/download/{raw_token}?platform=macos")

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    def test_token_single_use(self, client, tmp_path):
        """Token can only be used once."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, _ = _register_owner(client)

        from core.database import get_db
        from models.auth_token import AuthToken
        from models.user import User

        db = next(get_db())
        user = db.query(User).filter(User.email == "dl-owner@test.com").first()
        token_obj, raw_token = AuthToken.create_download_token(user.id)
        db.add(token_obj)
        db.commit()

        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp1 = client.get(f"{API}/agent/download/{raw_token}?platform=macos")
            resp2 = client.get(f"{API}/agent/download/{raw_token}?platform=macos")

        assert resp1.status_code == 200
        assert resp2.status_code == 400
        assert "expired" in resp2.json()["detail"].lower() or "invalid" in resp2.json()["detail"].lower()

    def test_invalid_token_returns_400(self, client):
        resp = client.get(f"{API}/agent/download/bogus-token-value?platform=macos")
        assert resp.status_code == 400


class TestEmailEnrollment:
    def test_enroll_email_requires_auth(self, client):
        resp = client.post(f"{API}/agent/enroll-email", json={
            "email": "user@test.com", "platform": "macos",
        })
        assert resp.status_code == 401

    def test_enroll_email_requires_admin(self, client):
        headers, _ = _register_viewer(client)
        resp = client.post(f"{API}/agent/enroll-email", json={
            "email": "user@test.com", "platform": "macos",
        }, headers=headers)
        assert resp.status_code == 403

    @patch("core.email.send_email")
    def test_enroll_email_success(self, mock_send, client):
        headers, _ = _register_owner(client)
        resp = client.post(f"{API}/agent/enroll-email", json={
            "email": "newuser@company.com", "platform": "windows",
            "interval": 600, "protocol": "http",
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "sent"
        assert data["email"] == "newuser@company.com"
        assert data["expires_in_hours"] == 72
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert "newuser@company.com" == call_args[0][0]
        assert "Detec Agent" in call_args[0][1]

    def test_enroll_email_smtp_not_configured(self, client):
        headers, _ = _register_owner(client)
        resp = client.post(f"{API}/agent/enroll-email", json={
            "email": "user@test.com", "platform": "macos",
        }, headers=headers)
        assert resp.status_code == 503
        assert "SMTP" in resp.json()["detail"]


class TestAgentKeyManagement:
    def test_get_key_no_key_yet(self, client):
        """New tenants (via register, not seed) start without an agent key."""
        headers, _ = _register_owner(client)
        resp = client.get(f"{API}/agent/key", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_key"] is False

    def test_get_key_after_download(self, client, tmp_path):
        """After a download, the tenant has a key."""
        pkg_dir = _create_fake_package(tmp_path, "DetecAgent-latest.pkg")
        headers, _ = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            client.get(f"{API}/agent/download?platform=macos", headers=headers)
        resp = client.get(f"{API}/agent/key", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_key"] is True
        assert len(data["key_prefix"]) == 8

    def test_rotate_key(self, client):
        headers, _ = _register_owner(client)
        resp1 = client.get(f"{API}/agent/key", headers=headers)
        old_prefix = resp1.json()["key_prefix"]

        resp2 = client.post(f"{API}/agent/key/rotate", headers=headers)
        assert resp2.status_code == 200
        data = resp2.json()
        assert len(data["agent_key"]) == 64
        assert "rotated" in data["message"].lower()

        resp3 = client.get(f"{API}/agent/key", headers=headers)
        new_prefix = resp3.json()["key_prefix"]
        assert new_prefix != old_prefix

    def test_rotate_requires_admin(self, client):
        headers, _ = _register_viewer(client)
        resp = client.post(f"{API}/agent/key/rotate", headers=headers)
        assert resp.status_code == 403


class TestAgentDownloadValidation:
    def test_invalid_platform_returns_422(self, client):
        headers, _ = _register_owner(client)
        resp = client.get(f"{API}/agent/download?platform=freebsd", headers=headers)
        assert resp.status_code == 422

    def test_missing_platform_returns_422(self, client):
        headers, _ = _register_owner(client)
        resp = client.get(f"{API}/agent/download", headers=headers)
        assert resp.status_code == 422

    def test_interval_too_low_returns_422(self, client):
        headers, _ = _register_owner(client)
        resp = client.get(f"{API}/agent/download?platform=macos&interval=5", headers=headers)
        assert resp.status_code == 422
