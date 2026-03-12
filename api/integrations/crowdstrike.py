"""CrowdStrike Falcon EDR provider implementation.

Covers two interfaces:
- EDRProvider (base.py): telemetry enrichment queries
- EnforcementProvider (enforcement_provider.py): delegated kill/contain via RTR
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx

from .base import EDRProvider
from .enforcement_provider import EnforcementProvider, EnforcementResult
from .types import (
    ProcessExecEvent,
    NetworkConnectEvent,
    FileChangeEvent,
)

logger = logging.getLogger(__name__)

RTR_SESSION_TIMEOUT = 30.0
RTR_COMMAND_TIMEOUT = 45.0


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

    async def _authed_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        retry_on_401: bool = True,
        timeout: float | None = None,
        **kwargs,
    ) -> httpx.Response:
        """Issue an authenticated request with one retry on 401 (token refresh)."""
        token = await self._ensure_token(client)
        headers = {**kwargs.pop("headers", {}), "Authorization": f"Bearer {token}"}
        resp = await client.request(
            method,
            f"{self._api_base}{path}",
            headers=headers,
            timeout=timeout or self._timeout,
            **kwargs,
        )
        if resp.status_code == 401 and retry_on_401:
            self._token = None
            self._token_expires_at = None
            token = await self._ensure_token(client)
            headers["Authorization"] = f"Bearer {token}"
            resp = await client.request(
                method,
                f"{self._api_base}{path}",
                headers=headers,
                timeout=timeout or self._timeout,
                **kwargs,
            )
        return resp

    # -- Host resolution -------------------------------------------------------

    async def resolve_endpoint_id(
        self, hostname: str, mac_address: str | None = None
    ) -> str | None:
        """Resolve hostname to CrowdStrike device_id using host search API."""
        async with httpx.AsyncClient() as client:
            try:
                _ = mac_address
                resp = await self._authed_request(
                    client,
                    "GET",
                    "/devices/queries/devices/v1",
                    params={"filter": f"hostname:*{hostname}*"},
                )
                resp.raise_for_status()
                data = resp.json()
                resources = data.get("resources", [])
                return resources[0] if resources else None
            except httpx.HTTPStatusError as e:
                logger.warning("CrowdStrike host lookup failed: %s", e)
                return None
            except Exception as e:
                logger.warning("CrowdStrike resolve_endpoint_id error: %s", e)
                return None

    # -- RTR (Real Time Response) methods --------------------------------------

    async def initiate_rtr_session(
        self, host_id: str, client: httpx.AsyncClient | None = None
    ) -> str | None:
        """Open an RTR session on the target host.

        Returns the session_id on success, None on failure.
        """
        async def _do(c: httpx.AsyncClient) -> str | None:
            try:
                resp = await self._authed_request(
                    c,
                    "POST",
                    "/real-time-response/entities/sessions/v1",
                    json={"device_id": host_id},
                    timeout=RTR_SESSION_TIMEOUT,
                )
                if resp.status_code == 409:
                    logger.warning(
                        "RTR session conflict on host %s (another session is active)", host_id
                    )
                    return None
                resp.raise_for_status()
                resources = resp.json().get("resources", [])
                if resources:
                    return resources[0].get("session_id")
                return None
            except httpx.HTTPStatusError as e:
                logger.warning("RTR session initiation failed for %s: %s", host_id, e)
                return None
            except Exception as e:
                logger.warning("RTR session error for %s: %s", host_id, e)
                return None

        if client:
            return await _do(client)
        async with httpx.AsyncClient() as c:
            return await _do(c)

    async def rtr_kill_process(
        self, session_id: str, pid: int, client: httpx.AsyncClient | None = None
    ) -> bool:
        """Kill a process via RTR admin command."""
        async def _do(c: httpx.AsyncClient) -> bool:
            try:
                resp = await self._authed_request(
                    c,
                    "POST",
                    "/real-time-response/entities/admin-command/v1",
                    json={
                        "session_id": session_id,
                        "base_command": "kill",
                        "command_string": f"kill {pid}",
                    },
                    timeout=RTR_COMMAND_TIMEOUT,
                )
                resp.raise_for_status()
                resources = resp.json().get("resources", [])
                if resources:
                    stderr = resources[0].get("stderr", "")
                    if stderr:
                        logger.warning("RTR kill stderr: %s", stderr)
                        return False
                    return True
                return False
            except Exception as e:
                logger.warning("RTR kill failed (session=%s, pid=%d): %s", session_id, pid, e)
                return False

        if client:
            return await _do(client)
        async with httpx.AsyncClient() as c:
            return await _do(c)

    async def rtr_network_contain(
        self, host_id: str, client: httpx.AsyncClient | None = None
    ) -> bool:
        """Network-contain a host via the host actions API.

        This does NOT require an RTR session; it uses the hosts API directly.
        """
        async def _do(c: httpx.AsyncClient) -> bool:
            try:
                resp = await self._authed_request(
                    c,
                    "POST",
                    "/devices/entities/devices-actions/v2",
                    params={"action_name": "contain"},
                    json={"ids": [host_id]},
                    timeout=RTR_SESSION_TIMEOUT,
                )
                resp.raise_for_status()
                return True
            except Exception as e:
                logger.warning("RTR network contain failed for %s: %s", host_id, e)
                return False

        if client:
            return await _do(client)
        async with httpx.AsyncClient() as c:
            return await _do(c)

    async def close_rtr_session(
        self, session_id: str, client: httpx.AsyncClient | None = None
    ) -> None:
        """Close an RTR session. Best-effort; failures are logged but not raised."""
        async def _do(c: httpx.AsyncClient) -> None:
            try:
                resp = await self._authed_request(
                    c,
                    "DELETE",
                    "/real-time-response/entities/sessions/v1",
                    params={"session_id": session_id},
                )
                if resp.status_code >= 400:
                    logger.debug("RTR session close returned %d", resp.status_code)
            except Exception as e:
                logger.debug("RTR session close error: %s", e)

        if client:
            await _do(client)
        else:
            async with httpx.AsyncClient() as c:
                await _do(c)

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
