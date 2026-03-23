"""SentinelOne EDR provider stub.

Covers two interfaces:
- EDRProvider (base.py): telemetry enrichment queries (stub; returns empty)
- EnforcementProvider (enforcement_provider.py): delegated kill/contain (stub; no-op)

A full implementation would use SentinelOne Deep Visibility and management APIs
for host resolution, process/network/file queries, and enforcement actions.
"""

from __future__ import annotations

import logging
from datetime import datetime

from .base import EDRProvider
from .enforcement_provider import EnforcementProvider, EnforcementResult
from .types import (
    ProcessExecEvent,
    NetworkConnectEvent,
    FileChangeEvent,
)

logger = logging.getLogger(__name__)


class SentinelOneProvider(EDRProvider):
    """SentinelOne EDR provider stub. Enrichment queries return empty until implemented."""

    @property
    def name(self) -> str:
        return "sentinelone"

    async def resolve_endpoint_id(
        self, hostname: str, mac_address: str | None = None
    ) -> str | None:
        """Resolve hostname to SentinelOne agent/device ID. Stub returns None."""
        _ = hostname
        _ = mac_address
        return None

    async def query_process_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[ProcessExecEvent]:
        """Query process events. Stub returns empty list."""
        _ = endpoint_id
        _ = start
        _ = end
        return []

    async def query_network_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[NetworkConnectEvent]:
        """Query network events. Stub returns empty list."""
        _ = endpoint_id
        _ = start
        _ = end
        return []

    async def query_file_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[FileChangeEvent]:
        """Query file events. Stub returns empty list."""
        _ = endpoint_id
        _ = start
        _ = end
        return []


class SentinelOneEnforcementProvider(EnforcementProvider):
    """SentinelOne enforcement provider stub. All actions return success=False with stub detail."""

    @property
    def name(self) -> str:
        return "sentinelone"

    async def kill_process(
        self, hostname: str, pid: int, process_name: str
    ) -> EnforcementResult:
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="kill_process",
            hostname=hostname,
            detail={"reason": "sentinelone_stub_not_implemented", "pid": pid},
        )

    async def block_network(self, hostname: str) -> EnforcementResult:
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="block_network",
            hostname=hostname,
            detail={"reason": "sentinelone_stub_not_implemented"},
        )

    async def quarantine_endpoint(self, hostname: str) -> EnforcementResult:
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="quarantine_endpoint",
            hostname=hostname,
            detail={"reason": "sentinelone_stub_not_implemented"},
        )

    async def available_for_endpoint(self, hostname: str) -> bool:
        """Stub: no endpoint is available until real implementation."""
        _ = hostname
        return False
