"""CrowdStrike Falcon EDR provider implementation."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from .base import EDRProvider
from .types import (
    ProcessExecEvent,
    NetworkConnectEvent,
    FileChangeEvent,
)

logger = logging.getLogger(__name__)


class CrowdStrikeProvider(EDRProvider):
    """CrowdStrike Falcon EDR provider using OAuth2 client credentials."""

    def __init__(
        self,
        api_base: str,
        client_id: str,
        client_secret: str,
        timeout: float = 30.0,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._client_id = client_id
        self._client_secret = client_secret
        self._timeout = timeout
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def name(self) -> str:
        return "crowdstrike"

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        """Obtain or refresh OAuth2 bearer token."""
        now = datetime.utcnow()
        if self._token and self._token_expires_at and now < self._token_expires_at:
            return self._token

        url = f"{self._api_base}/oauth2/token"
        resp = await client.post(
            url,
            data={
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        expires_in = data.get("expires_in", 1799)
        self._token_expires_at = now + timedelta(seconds=expires_in - 60)
        return self._token

    async def resolve_endpoint_id(
        self, hostname: str, mac_address: str | None = None
    ) -> str | None:
        """Resolve hostname to CrowdStrike device_id using host search API."""
        async with httpx.AsyncClient() as client:
            try:
                token = await self._ensure_token(client)
                # TODO: implement actual CrowdStrike API calls
                # GET /devices/queries/devices/v1 with filter: hostname:*hostname*
                # Returns device IDs; use first match or exact match
                _ = mac_address
                url = f"{self._api_base}/devices/queries/devices/v1"
                resp = await client.get(
                    url,
                    params={"filter": f"hostname:*{hostname}*"},
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=self._timeout,
                )
                resp.raise_for_status()
                data = resp.json()
                resources = data.get("resources", [])
                if resources:
                    return resources[0]
                return None
            except httpx.HTTPStatusError as e:
                logger.warning("CrowdStrike host lookup failed: %s", e)
                return None
            except Exception as e:
                logger.warning("CrowdStrike resolve_endpoint_id error: %s", e)
                return None

    async def query_process_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[ProcessExecEvent]:
        """Query ProcessRollup2 events for the endpoint in the time window."""
        async with httpx.AsyncClient() as client:
            try:
                token = await self._ensure_token(client)
                # TODO: implement actual CrowdStrike API calls
                # Query ProcessRollup2 events with time filter and device_id
                _ = endpoint_id
                _ = start
                _ = end
                _ = token
                return []
            except Exception as e:
                logger.warning("CrowdStrike query_process_events error: %s", e)
                return []

    async def query_network_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[NetworkConnectEvent]:
        """Query NetworkConnectIP4/IP6 events for the endpoint in the time window."""
        async with httpx.AsyncClient() as client:
            try:
                token = await self._ensure_token(client)
                # TODO: implement actual CrowdStrike API calls
                # Query NetworkConnectIP4/IP6 events with time filter and device_id
                _ = endpoint_id
                _ = start
                _ = end
                _ = token
                return []
            except Exception as e:
                logger.warning("CrowdStrike query_network_events error: %s", e)
                return []

    async def query_file_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[FileChangeEvent]:
        """Query file change events for the endpoint in the time window."""
        async with httpx.AsyncClient() as client:
            try:
                token = await self._ensure_token(client)
                # TODO: implement actual CrowdStrike API calls
                _ = endpoint_id
                _ = start
                _ = end
                _ = token
                return []
            except Exception as e:
                logger.warning("CrowdStrike query_file_events error: %s", e)
                return []
