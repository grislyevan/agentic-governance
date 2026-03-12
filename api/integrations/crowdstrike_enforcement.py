"""CrowdStrike Falcon enforcement provider.

Implements EnforcementProvider using the RTR methods on CrowdStrikeProvider.
Handles the full lifecycle: resolve host -> open session -> execute -> close.
"""

from __future__ import annotations

import logging

import httpx

from .crowdstrike import CrowdStrikeProvider
from .enforcement_provider import EnforcementProvider, EnforcementResult

logger = logging.getLogger(__name__)


class CrowdStrikeEnforcementProvider(EnforcementProvider):
    """Delegated enforcement via CrowdStrike Falcon RTR and host actions."""

    def __init__(self, cs_provider: CrowdStrikeProvider) -> None:
        self._cs = cs_provider

    @property
    def name(self) -> str:
        return "crowdstrike"

    async def _resolve_host(self, hostname: str) -> str | None:
        return await self._cs.resolve_endpoint_id(hostname)

    async def kill_process(
        self, hostname: str, pid: int, process_name: str
    ) -> EnforcementResult:
        host_id = await self._resolve_host(hostname)
        if not host_id:
            return EnforcementResult(
                success=False,
                provider=self.name,
                action="kill_process",
                hostname=hostname,
                detail={"reason": "host_not_found", "pid": pid, "process_name": process_name},
            )

        async with httpx.AsyncClient() as client:
            session_id = await self._cs.initiate_rtr_session(host_id, client=client)
            if not session_id:
                return EnforcementResult(
                    success=False,
                    provider=self.name,
                    action="kill_process",
                    hostname=hostname,
                    detail={"reason": "rtr_session_failed", "host_id": host_id, "pid": pid},
                )

            try:
                killed = await self._cs.rtr_kill_process(session_id, pid, client=client)
                return EnforcementResult(
                    success=killed,
                    provider=self.name,
                    action="kill_process",
                    hostname=hostname,
                    detail={
                        "host_id": host_id,
                        "session_id": session_id,
                        "pid": pid,
                        "process_name": process_name,
                        "reason": None if killed else "kill_command_failed",
                    },
                )
            finally:
                await self._cs.close_rtr_session(session_id, client=client)

    async def block_network(self, hostname: str) -> EnforcementResult:
        host_id = await self._resolve_host(hostname)
        if not host_id:
            return EnforcementResult(
                success=False,
                provider=self.name,
                action="block_network",
                hostname=hostname,
                detail={"reason": "host_not_found"},
            )

        async with httpx.AsyncClient() as client:
            contained = await self._cs.rtr_network_contain(host_id, client=client)
            return EnforcementResult(
                success=contained,
                provider=self.name,
                action="block_network",
                hostname=hostname,
                detail={
                    "host_id": host_id,
                    "reason": None if contained else "contain_failed",
                },
            )

    async def quarantine_endpoint(self, hostname: str) -> EnforcementResult:
        result = await self.block_network(hostname)
        result.action = "quarantine_endpoint"
        return result

    async def available_for_endpoint(self, hostname: str) -> bool:
        host_id = await self._resolve_host(hostname)
        return host_id is not None
