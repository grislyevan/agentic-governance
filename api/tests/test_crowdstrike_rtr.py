"""Tests for CrowdStrike RTR methods with mocked httpx."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.crowdstrike import CrowdStrikeProvider
from integrations.crowdstrike_enforcement import CrowdStrikeEnforcementProvider


@pytest.fixture
def provider():
    return CrowdStrikeProvider(
        api_base="https://api.crowdstrike.com",
        client_id="test-client-id",
        client_secret="test-client-secret",
    )


def _make_response(status_code: int, json_data: dict):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp
        )
    return resp


def _setup_mock_client(mock_client_cls):
    """Configure mock AsyncClient: post for oauth, request for all other calls."""
    mock_client = AsyncMock()
    mock_client_cls.return_value.__aenter__.return_value = mock_client
    return mock_client


@pytest.mark.asyncio
async def test_initiate_rtr_session_success(provider):
    """POST to sessions/v1 returns session_id."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(201, {"resources": [{"session_id": "sess-abc-123"}]})
        )

        result = await provider.initiate_rtr_session("device-xyz")
        assert result == "sess-abc-123"
        mock_client.post.assert_called_once()
        mock_client.request.assert_called_once()


@pytest.mark.asyncio
async def test_initiate_rtr_session_conflict_409(provider):
    """Returns None on 409 (another session active)."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(409, {"resources": []})
        )

        result = await provider.initiate_rtr_session("device-xyz")
        assert result is None


@pytest.mark.asyncio
async def test_rtr_kill_process_success(provider):
    """POST admin-command returns success."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": [{"stderr": ""}]})
        )

        result = await provider.rtr_kill_process("sess-123", 1234)
        assert result is True


@pytest.mark.asyncio
async def test_rtr_kill_process_stderr_failure(provider):
    """Kill with stderr returns False."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": [{"stderr": "Access denied"}]})
        )

        result = await provider.rtr_kill_process("sess-123", 1234)
        assert result is False


@pytest.mark.asyncio
async def test_rtr_network_contain_success(provider):
    """POST devices-actions with contain action succeeds."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(return_value=_make_response(200, {}))

        result = await provider.rtr_network_contain("host-id-456")
        assert result is True


@pytest.mark.asyncio
async def test_rtr_network_contain_failure(provider):
    """Contain returns False on error."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server error",
                request=MagicMock(),
                response=_make_response(500, {"errors": []}),
            )
        )

        result = await provider.rtr_network_contain("host-id-456")
        assert result is False


@pytest.mark.asyncio
async def test_close_rtr_session_success(provider):
    """DELETE session is best-effort."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(return_value=_make_response(200, {}))

        await provider.close_rtr_session("sess-123")
        assert mock_client.request.call_count >= 1
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "DELETE"


@pytest.mark.asyncio
async def test_authed_request_retries_on_401(provider):
    """First call gets 401, token refreshed, retry succeeds."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_resp_401 = _make_response(401, {"errors": [{"message": "Unauthorized"}]})
        mock_client.post = AsyncMock(
            side_effect=[
                _make_response(201, {"access_token": "tok1", "expires_in": 1799}),
                _make_response(201, {"access_token": "tok2", "expires_in": 1799}),
            ]
        )
        mock_client.request = AsyncMock(
            side_effect=[
                mock_resp_401,
                _make_response(200, {"resources": ["device-123"]}),
            ]
        )

        result = await provider.resolve_endpoint_id("my-host")
        assert result == "device-123"
        assert mock_client.post.call_count == 2
        assert mock_client.request.call_count == 2


@pytest.mark.asyncio
async def test_crowdstrike_enforcement_provider_kill():
    """Full CrowdStrikeEnforcementProvider.kill_process flow."""
    cs_provider = CrowdStrikeProvider(
        api_base="https://api.crowdstrike.com",
        client_id="test-client-id",
        client_secret="test-client-secret",
    )
    enf_provider = CrowdStrikeEnforcementProvider(cs_provider)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            side_effect=[
                _make_response(200, {"resources": ["device-abc"]}),
                _make_response(201, {"resources": [{"session_id": "sess-xyz"}]}),
                _make_response(200, {"resources": [{"stderr": ""}]}),
                _make_response(200, {}),
            ]
        )

        result = await enf_provider.kill_process("laptop-01", 9999, "malware.exe")

        assert result.success is True
        assert result.provider == "crowdstrike"
        assert result.action == "kill_process"
        assert result.hostname == "laptop-01"
        assert result.detail.get("pid") == 9999
        assert result.detail.get("process_name") == "malware.exe"


@pytest.mark.asyncio
async def test_crowdstrike_enforcement_provider_available():
    """available_for_endpoint returns True when host found."""
    cs_provider = CrowdStrikeProvider(
        api_base="https://api.crowdstrike.com",
        client_id="test-client-id",
        client_secret="test-client-secret",
    )
    enf_provider = CrowdStrikeEnforcementProvider(cs_provider)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = _setup_mock_client(mock_client_cls)
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {"access_token": "tok", "expires_in": 1799})
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": ["device-123"]})
        )

        result = await enf_provider.available_for_endpoint("known-host")
        assert result is True
