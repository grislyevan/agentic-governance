"""Tests for the agent download router."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from tests.conftest import API, _auth_header, register_user


def _register_owner(client):
    """Register a user with owner role and return (auth_header, api_key)."""
    tokens = register_user(client, "dl-owner@test.com", tenant_name="DL Org")
    return _auth_header(tokens["access_token"]), tokens["api_key"]


def _register_viewer(client):
    """Register a viewer-role user. Owner creates the tenant, then we
    downgrade for testing role restrictions."""
    from core.database import get_db
    from models.user import User

    tokens = register_user(client, "dl-viewer@test.com", tenant_name="Viewer Org")
    # Patch the user to viewer role directly in DB
    db = next(get_db())
    user = db.query(User).filter(User.email == "dl-viewer@test.com").first()
    user.role = "viewer"
    db.commit()
    return _auth_header(tokens["access_token"]), tokens["api_key"]


class TestAgentDownloadAuth:
    def test_unauthenticated_returns_401(self, client):
        resp = client.get(f"{API}/agent/download?platform=macos")
        assert resp.status_code == 401

    def test_viewer_role_returns_403(self, client):
        _, api_key = _register_viewer(client)
        resp = client.get(
            f"{API}/agent/download?platform=macos",
            headers={"X-Api-Key": api_key},
        )
        assert resp.status_code == 403

    def test_jwt_without_api_key_returns_400(self, client):
        """JWT auth works for role check but X-Api-Key is required to embed."""
        auth_header, _ = _register_owner(client)
        resp = client.get(
            f"{API}/agent/download?platform=macos",
            headers=auth_header,
        )
        assert resp.status_code == 400
        assert "X-Api-Key" in resp.json()["detail"]


class TestAgentDownloadMissingPackage:
    def test_missing_package_returns_404(self, client):
        _, api_key = _register_owner(client)
        resp = client.get(
            f"{API}/agent/download?platform=linux",
            headers={"X-Api-Key": api_key},
        )
        assert resp.status_code == 404
        assert "pre-built" in resp.json()["detail"].lower()


class TestAgentDownloadSuccess:
    def _create_fake_package(self, tmp_path: Path, name: str) -> Path:
        pkg_dir = tmp_path / "dist" / "packages"
        pkg_dir.mkdir(parents=True, exist_ok=True)
        pkg_file = pkg_dir / name
        pkg_file.write_bytes(b"fake-installer-content")
        return pkg_dir

    def test_download_macos_returns_zip(self, client, tmp_path):
        pkg_dir = self._create_fake_package(tmp_path, "DetecAgent-latest.pkg")

        _, api_key = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(
                f"{API}/agent/download?platform=macos",
                headers={"X-Api-Key": api_key},
            )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"
        assert "detec-agent-macos.zip" in resp.headers.get("content-disposition", "")

        zf = zipfile.ZipFile(BytesIO(resp.content))
        names = zf.namelist()
        assert "DetecAgent-latest.pkg" in names
        assert "agent.env" in names
        assert "collector.json" in names
        assert "README.md" in names

        env_content = zf.read("agent.env").decode()
        assert "AGENTIC_GOV_API_URL=" in env_content
        assert f"AGENTIC_GOV_API_KEY={api_key}" in env_content
        assert "AGENTIC_GOV_INTERVAL=300" in env_content
        assert "AGENTIC_GOV_PROTOCOL=http" in env_content

    def test_download_windows_returns_zip(self, client, tmp_path):
        pkg_dir = self._create_fake_package(tmp_path, "detec-agent.zip")

        _, api_key = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(
                f"{API}/agent/download?platform=windows&interval=600&protocol=tcp",
                headers={"X-Api-Key": api_key},
            )

        assert resp.status_code == 200

        zf = zipfile.ZipFile(BytesIO(resp.content))
        names = zf.namelist()
        assert "detec-agent.zip" in names
        assert "collector.json" in names

        import json
        cfg = json.loads(zf.read("collector.json"))
        assert cfg["interval"] == 600
        assert cfg["protocol"] == "tcp"
        assert "gateway_port" in cfg
        assert cfg["api_key"] == api_key

    def test_download_linux_returns_zip(self, client, tmp_path):
        pkg_dir = self._create_fake_package(tmp_path, "detec-agent-linux.tar.gz")

        _, api_key = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(
                f"{API}/agent/download?platform=linux",
                headers={"X-Api-Key": api_key},
            )

        assert resp.status_code == 200
        zf = zipfile.ZipFile(BytesIO(resp.content))
        assert "detec-agent-linux.tar.gz" in zf.namelist()

    def test_custom_interval_and_protocol(self, client, tmp_path):
        pkg_dir = self._create_fake_package(tmp_path, "DetecAgent-latest.pkg")

        _, api_key = _register_owner(client)
        with patch("routers.agent_download._DIST_DIR", pkg_dir):
            resp = client.get(
                f"{API}/agent/download?platform=macos&interval=60&protocol=tcp",
                headers={"X-Api-Key": api_key},
            )

        assert resp.status_code == 200
        zf = zipfile.ZipFile(BytesIO(resp.content))

        env_content = zf.read("agent.env").decode()
        assert "AGENTIC_GOV_INTERVAL=60" in env_content
        assert "AGENTIC_GOV_PROTOCOL=tcp" in env_content
        assert "AGENTIC_GOV_GATEWAY_HOST=" in env_content
        assert "AGENTIC_GOV_GATEWAY_PORT=" in env_content


class TestAgentDownloadValidation:
    def test_invalid_platform_returns_422(self, client):
        _, api_key = _register_owner(client)
        resp = client.get(
            f"{API}/agent/download?platform=freebsd",
            headers={"X-Api-Key": api_key},
        )
        assert resp.status_code == 422

    def test_missing_platform_returns_422(self, client):
        _, api_key = _register_owner(client)
        resp = client.get(
            f"{API}/agent/download",
            headers={"X-Api-Key": api_key},
        )
        assert resp.status_code == 422

    def test_interval_too_low_returns_422(self, client):
        _, api_key = _register_owner(client)
        resp = client.get(
            f"{API}/agent/download?platform=macos&interval=5",
            headers={"X-Api-Key": api_key},
        )
        assert resp.status_code == 422
