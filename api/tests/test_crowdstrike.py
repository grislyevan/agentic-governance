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
            return_value=_make_response(
                201,
                {
                    "access_token": "bearer-token-123",
                    "expires_in": 1799,
                },
            )
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
            return_value=_make_response(
                201,
                {
                    "access_token": "bearer-token-123",
                    "expires_in": 1799,
                },
            )
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
            return_value=_make_response(
                201,
                {
                    "access_token": "cached-token",
                    "expires_in": 1799,
                },
            )
        )
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": ["dev-1"]})
        )

        await provider.resolve_endpoint_id("host1")
        await provider.resolve_endpoint_id("host2")

        assert mock_client.post.call_count == 1


@pytest.mark.asyncio
async def test_query_process_events_empty_when_no_ids(provider):
    """query_process_events returns empty list when no event IDs are found."""
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        # Auth token request
        mock_client.post = AsyncMock(
            return_value=_make_response(
                200,
                {
                    "access_token": "tok",
                    "expires_in": 1799,
                },
            )
        )
        # Event ID query returns no resources
        mock_client.request = AsyncMock(
            return_value=_make_response(200, {"resources": []})
        )

        start = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, 12, 10, 0, tzinfo=timezone.utc)
        result = await provider.query_process_events("device-1", start, end)
        assert result == []


@pytest.mark.asyncio
async def test_query_process_events_maps_to_dataclass(provider):
    """query_process_events maps ProcessRollup2 payloads to ProcessExecEvent objects."""
    from integrations.types import ProcessExecEvent

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        # Auth token
        mock_client.post = AsyncMock(
            return_value=_make_response(
                200,
                {
                    "access_token": "tok",
                    "expires_in": 1799,
                },
            )
        )
        # First request: ID query; second: entity fetch
        mock_client.request = AsyncMock(
            side_effect=[
                _make_response(200, {"resources": ["evt-001"]}),  # ID query
                _make_response(
                    200,
                    {
                        "resources": [
                            {  # entity fetch
                                "event_simpleName": "ProcessRollup2",
                                "timestamp": "2026-03-10T12:01:00Z",
                                "TargetProcessId_decimal": "1234",
                                "ParentProcessId_decimal": "5678",
                                "ImageFileName": "\\Device\\claude_code.exe",
                                "CommandLine": "claude --help",
                                "UserName": "alice",
                                "SHA256HashData": "abc123",
                            }
                        ]
                    },
                ),
            ]
        )

        start = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, 12, 10, 0, tzinfo=timezone.utc)
        result = await provider.query_process_events("device-1", start, end)
        assert len(result) == 1
        ev = result[0]
        assert isinstance(ev, ProcessExecEvent)
        assert ev.pid == 1234
        assert ev.ppid == 5678
        assert ev.name == "claude_code.exe"
        assert ev.cmdline == "claude --help"
        assert ev.username == "alice"
        assert ev.binary_hash == "abc123"


@pytest.mark.asyncio
async def test_query_network_events_maps_to_dataclass(provider):
    """query_network_events maps NetworkConnectIP4 payloads to NetworkConnectEvent objects."""
    from integrations.types import NetworkConnectEvent

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(
            return_value=_make_response(
                200, {"access_token": "tok", "expires_in": 1799}
            )
        )
        mock_client.request = AsyncMock(
            side_effect=[
                _make_response(200, {"resources": ["net-001"]}),
                _make_response(
                    200,
                    {
                        "resources": [
                            {
                                "event_simpleName": "NetworkConnectIP4",
                                "timestamp": "2026-03-10T12:02:00Z",
                                "ContextProcessId_decimal": "2345",
                                "ImageFileName": "/usr/local/bin/ollama",
                                "RemoteAddressIP4": "127.0.0.1",
                                "RemotePort_decimal": "11434",
                                "LocalPort_decimal": "54321",
                                "Protocol": "TCP",
                            }
                        ]
                    },
                ),
            ]
        )

        start = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, 12, 10, 0, tzinfo=timezone.utc)
        result = await provider.query_network_events("device-1", start, end)
        assert len(result) == 1
        ev = result[0]
        assert isinstance(ev, NetworkConnectEvent)
        assert ev.pid == 2345
        assert ev.remote_addr == "127.0.0.1"
        assert ev.remote_port == 11434
        assert ev.process_name == "ollama"


@pytest.mark.asyncio
async def test_query_file_events_maps_to_dataclass(provider):
    """query_file_events maps FileWrite payloads to FileChangeEvent objects."""
    from integrations.types import FileChangeEvent

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post = AsyncMock(
            return_value=_make_response(
                200, {"access_token": "tok", "expires_in": 1799}
            )
        )
        mock_client.request = AsyncMock(
            side_effect=[
                _make_response(200, {"resources": ["file-001"]}),
                _make_response(
                    200,
                    {
                        "resources": [
                            {
                                "event_simpleName": "FileWrite",
                                "timestamp": "2026-03-10T12:03:00Z",
                                "ContextProcessId_decimal": "3456",
                                "ImageFileName": "/usr/local/bin/cursor",
                                "TargetFileName": "/home/user/project/main.py",
                            }
                        ]
                    },
                ),
            ]
        )

        start = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 10, 12, 10, 0, tzinfo=timezone.utc)
        result = await provider.query_file_events("device-1", start, end)
        assert len(result) == 1
        ev = result[0]
        assert isinstance(ev, FileChangeEvent)
        assert ev.pid == 3456
        assert ev.path == "/home/user/project/main.py"
        assert ev.action == "modified"
        assert ev.process_name == "cursor"
