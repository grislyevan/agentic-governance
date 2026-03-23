"""Tests for CrowdStrike EDR provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from integrations.crowdstrike import CrowdStrikeProvider


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
    return resp


@pytest.mark.asyncio
async def test_auth_token_obtained(provider):
    """Provider obtains OAuth2 token via client credentials."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_client.post = AsyncMock(
            return_value=_make_response(201, {
                "access_token": "bearer-token-123",
                "expires_in": 1799,
            })
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": ["device-abc-123"]})
        )

        result = await provider.resolve_endpoint_id("my-host")
        assert result == "device-abc-123"
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "oauth2/token" in str(call_args[0][0])
        assert call_args[1]["data"]["client_id"] == "test-client-id"


@pytest.mark.asyncio
async def test_resolve_endpoint_id_returns_none_when_no_devices(provider):
    """When host search returns no devices, resolve_endpoint_id returns None."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_client.post = AsyncMock(
            return_value=_make_response(201, {
                "access_token": "bearer-token-123",
                "expires_in": 1799,
            })
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": []})
        )

        result = await provider.resolve_endpoint_id("unknown-host")
        assert result is None


@pytest.mark.asyncio
async def test_auth_failure_returns_none(provider):
    """When auth fails, resolve_endpoint_id returns None (graceful handling)."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_client.post = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=MagicMock(),
                response=mock_resp,
            )
        )

        result = await provider.resolve_endpoint_id("my-host")
        assert result is None


@pytest.mark.asyncio
async def test_token_caching(provider):
    """Token is cached and reused within expiry window."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client

        mock_client.post = AsyncMock(
            return_value=_make_response(201, {
                "access_token": "cached-token",
                "expires_in": 1799,
            })
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": ["dev-1"]})
        )

        await provider.resolve_endpoint_id("host1")
        await provider.resolve_endpoint_id("host2")

        assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_query_process_events_returns_empty(provider):
    """query_process_events returns empty list (stub implementation)."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(
            return_value=_make_response(201, {
                "access_token": "tok",
                "expires_in": 1799,
            })
        )

        start = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, 12, 10, 0, tzinfo=timezone.utc)
        result = await provider.query_process_events("device-1", start, end)
        assert result == []
