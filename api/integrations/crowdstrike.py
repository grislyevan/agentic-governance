"""CrowdStrike Falcon EDR provider implementation.

Covers two interfaces:
- EDRProvider (base.py): telemetry enrichment queries
- EnforcementProvider (enforcement_provider.py): delegated kill/contain via RTR
"""

from __future__ import annotations

import logging
import re
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

# Sanitize hostname: only allow DNS-label characters, reject anything else
_SAFE_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9.\-]{1,253}$")


def _parse_cs_timestamp(ts_value: object, fallback: datetime) -> datetime:
    """Parse a CrowdStrike timestamp field to a ``datetime``.

    CrowdStrike event payloads use ISO-8601 strings (e.g. ``2024-01-01T12:00:00Z``)
    or Unix epoch integers/floats in ``*_decimal`` fields.  Returns *fallback*
    on any parsing failure.
    """
    from datetime import timezone as _tz

    if not ts_value:
        return fallback
    if isinstance(ts_value, (int, float)):
        try:
            return datetime.fromtimestamp(float(ts_value), tz=_tz.utc)
        except (ValueError, OSError, OverflowError):
            return fallback
    if isinstance(ts_value, str):
        clean = ts_value.strip().rstrip("Z")
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
        ):
            try:
                from datetime import timezone as _tz2

                return datetime.strptime(clean, fmt).replace(tzinfo=_tz2.utc)
            except ValueError:
                continue
    return fallback


def _sanitize_fql_hostname(hostname: str) -> str | None:
    """Return hostname if safe for FQL interpolation, else None."""
    if _SAFE_HOSTNAME_RE.match(hostname):
        return hostname
    return None


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
                safe_hostname = _sanitize_fql_hostname(hostname)
                if not safe_hostname:
                    logger.warning(
                        "Skipping CrowdStrike lookup: invalid hostname %r", hostname
                    )
                    return None
                resp = await self._authed_request(
                    client,
                    "GET",
                    "/devices/queries/devices/v1",
                    params={"filter": f"hostname:*{safe_hostname}*"},
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
                        "RTR session conflict on host %s (another session is active)",
                        host_id,
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
                logger.warning(
                    "RTR kill failed (session=%s, pid=%d): %s", session_id, pid, e
                )
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

    # -- Event query helpers ---------------------------------------------------

    def _fmt_timestamp(self, dt: datetime) -> str:
        """Format a datetime as a CrowdStrike FQL-compatible RFC3339 string."""
        # CrowdStrike FQL uses RFC3339; ensure UTC Z suffix.
        if dt.tzinfo is None:
            ts = dt.isoformat() + "Z"
        else:
            ts = dt.astimezone(__import__("datetime").timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
        return ts

    async def _query_event_ids(
        self,
        client: httpx.AsyncClient,
        fql_filter: str,
        limit: int = 100,
    ) -> list[str]:
        """Query Falcon Event Search for event IDs matching *fql_filter*.

        Returns a list of event IDs (strings).  Empty list on any error.
        """
        try:
            resp = await self._authed_request(
                client,
                "GET",
                "/events/queries/events/v1",
                params={"filter": fql_filter, "limit": limit},
            )
            resp.raise_for_status()
            return resp.json().get("resources", []) or []
        except Exception as exc:
            logger.warning("CrowdStrike event ID query failed: %s", exc)
            return []

    async def _fetch_event_details(
        self,
        client: httpx.AsyncClient,
        event_ids: list[str],
    ) -> list[dict]:
        """Fetch full event payloads for *event_ids* via the Event Search entities API.

        Returns a list of raw event dicts (the CrowdStrike EventBody objects).
        """
        if not event_ids:
            return []
        try:
            resp = await self._authed_request(
                client,
                "GET",
                "/events/entities/events/v1",
                params=[("ids", eid) for eid in event_ids],
            )
            resp.raise_for_status()
            return resp.json().get("resources", []) or []
        except Exception as exc:
            logger.warning("CrowdStrike event entity fetch failed: %s", exc)
            return []

    # -- EDRProvider interface -------------------------------------------------

    async def query_process_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[ProcessExecEvent]:
        """Query ProcessRollup2 events for the endpoint in the time window.

        Uses the CrowdStrike Event Search API to find process execution events
        for the given device and time range, then maps the raw payloads to the
        ``ProcessExecEvent`` dataclass required by the enrichment pipeline.
        """
        async with httpx.AsyncClient() as client:
            try:
                start_str = self._fmt_timestamp(start)
                end_str = self._fmt_timestamp(end)
                fql = (
                    f"device_id:'{endpoint_id}'"
                    f"+event_simpleName:'ProcessRollup2'"
                    f"+timestamp:>='{start_str}'"
                    f"+timestamp:<='{end_str}'"
                )
                event_ids = await self._query_event_ids(client, fql)
                if not event_ids:
                    return []
                raw_events = await self._fetch_event_details(client, event_ids)
                results: list[ProcessExecEvent] = []
                for ev in raw_events:
                    try:
                        ts_str = ev.get("timestamp") or ev.get(
                            "ProcessStartTime_decimal", ""
                        )
                        ts = _parse_cs_timestamp(ts_str, start)
                        results.append(
                            ProcessExecEvent(
                                timestamp=ts,
                                pid=int(
                                    ev.get("TargetProcessId_decimal")
                                    or ev.get("RawProcessId_decimal")
                                    or 0
                                ),
                                ppid=int(ev.get("ParentProcessId_decimal") or 0),
                                name=ev.get("ImageFileName", "")
                                .split("\\")[-1]
                                .split("/")[-1],
                                cmdline=ev.get("CommandLine", ""),
                                username=ev.get("UserName"),
                                binary_path=ev.get("ImageFileName"),
                                binary_hash=ev.get("SHA256HashData"),
                            )
                        )
                    except (KeyError, ValueError, TypeError) as map_err:
                        logger.debug("ProcessRollup2 mapping error: %s", map_err)
                return results
            except Exception as exc:
                logger.warning("CrowdStrike query_process_events error: %s", exc)
                return []

    async def query_network_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[NetworkConnectEvent]:
        """Query NetworkConnectIP4/IP6 events for the endpoint in the time window.

        Maps CrowdStrike ``NetworkConnectIP4`` and ``NetworkConnectIP6`` events
        to the ``NetworkConnectEvent`` dataclass.
        """
        async with httpx.AsyncClient() as client:
            try:
                start_str = self._fmt_timestamp(start)
                end_str = self._fmt_timestamp(end)
                # Query both IPv4 and IPv6 connect events
                fql = (
                    f"device_id:'{endpoint_id}'"
                    f"+event_simpleName:['NetworkConnectIP4','NetworkConnectIP6']"
                    f"+timestamp:>='{start_str}'"
                    f"+timestamp:<='{end_str}'"
                )
                event_ids = await self._query_event_ids(client, fql)
                if not event_ids:
                    return []
                raw_events = await self._fetch_event_details(client, event_ids)
                results: list[NetworkConnectEvent] = []
                for ev in raw_events:
                    try:
                        ts_str = ev.get("timestamp", "")
                        ts = _parse_cs_timestamp(ts_str, start)
                        remote_addr = (
                            ev.get("RemoteAddressIP4")
                            or ev.get("RemoteAddressIP6")
                            or ""
                        )
                        results.append(
                            NetworkConnectEvent(
                                timestamp=ts,
                                pid=int(ev.get("ContextProcessId_decimal") or 0),
                                process_name=ev.get("ImageFileName", "")
                                .split("\\")[-1]
                                .split("/")[-1],
                                remote_addr=remote_addr,
                                remote_port=int(ev.get("RemotePort_decimal") or 0),
                                local_port=int(ev.get("LocalPort_decimal") or 0),
                                protocol=ev.get("Protocol", "tcp").lower(),
                                sni=ev.get("ServerName"),
                            )
                        )
                    except (KeyError, ValueError, TypeError) as map_err:
                        logger.debug("NetworkConnect mapping error: %s", map_err)
                return results
            except Exception as exc:
                logger.warning("CrowdStrike query_network_events error: %s", exc)
                return []

    async def query_file_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[FileChangeEvent]:
        """Query file change events for the endpoint in the time window.

        Maps CrowdStrike ``MotionDetection``, ``EndOfProcess``, or
        ``FileWrite``-style events (``DirectoryCreate``, ``FileWrite``, etc.)
        to the ``FileChangeEvent`` dataclass.
        """
        async with httpx.AsyncClient() as client:
            try:
                start_str = self._fmt_timestamp(start)
                end_str = self._fmt_timestamp(end)
                fql = (
                    f"device_id:'{endpoint_id}'"
                    f"+event_simpleName:['DirectoryCreate','FileWrite','FileDelete','FileDuplicate','FileRename']"
                    f"+timestamp:>='{start_str}'"
                    f"+timestamp:<='{end_str}'"
                )
                event_ids = await self._query_event_ids(client, fql)
                if not event_ids:
                    return []
                raw_events = await self._fetch_event_details(client, event_ids)
                _ACTION_MAP = {
                    "DirectoryCreate": "created",
                    "FileWrite": "modified",
                    "FileDelete": "deleted",
                    "FileDuplicate": "created",
                    "FileRename": "renamed",
                }
                results: list[FileChangeEvent] = []
                for ev in raw_events:
                    try:
                        ts_str = ev.get("timestamp", "")
                        ts = _parse_cs_timestamp(ts_str, start)
                        event_name = ev.get("event_simpleName", "FileWrite")
                        action = _ACTION_MAP.get(event_name, "modified")
                        results.append(
                            FileChangeEvent(
                                timestamp=ts,
                                pid=int(ev.get("ContextProcessId_decimal") or 0)
                                or None,
                                path=ev.get("TargetFileName")
                                or ev.get("TargetDirectoryName")
                                or "",
                                action=action,
                                process_name=ev.get("ImageFileName", "")
                                .split("\\")[-1]
                                .split("/")[-1]
                                or None,
                            )
                        )
                    except (KeyError, ValueError, TypeError) as map_err:
                        logger.debug("FileChange mapping error: %s", map_err)
                return results
            except Exception as exc:
                logger.warning("CrowdStrike query_file_events error: %s", exc)
                return []
