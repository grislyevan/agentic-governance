"""Microsoft Intune enforcement provider stub.

Implements EnforcementProvider for Windows endpoints managed by Intune.
Uses Microsoft Graph API for device management and remediation.
"""

from __future__ import annotations

import logging

from core.config import settings
from .enforcement_provider import EnforcementProvider, EnforcementResult

logger = logging.getLogger(__name__)


class IntuneEnforcementProvider(EnforcementProvider):
    """Delegated enforcement via Microsoft Intune / Graph API."""

    @property
    def name(self) -> str:
        return "intune"

    def _configured(self) -> bool:
        return bool(
            settings.intune_tenant_id
            and settings.intune_client_id
            and settings.intune_client_secret
        )

    async def kill_process(
        self, hostname: str, pid: int, process_name: str
    ) -> EnforcementResult:
        if not self._configured():
            logger.warning("Intune integration not yet configured")
            return EnforcementResult(
                success=False,
                provider=self.name,
                action="kill_process",
                hostname=hostname,
                detail={"reason": "not_configured", "pid": pid, "process_name": process_name},
            )
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="kill_process",
            hostname=hostname,
            detail={"reason": "stub", "pid": pid, "process_name": process_name},
        )

    async def block_network(self, hostname: str) -> EnforcementResult:
        if not self._configured():
            logger.warning("Intune integration not yet configured")
            return EnforcementResult(
                success=False,
                provider=self.name,
                action="block_network",
                hostname=hostname,
                detail={"reason": "not_configured"},
            )
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="block_network",
            hostname=hostname,
            detail={"reason": "stub"},
        )

    async def quarantine_endpoint(self, hostname: str) -> EnforcementResult:
        if not self._configured():
            logger.warning("Intune integration not yet configured")
            return EnforcementResult(
                success=False,
                provider=self.name,
                action="quarantine_endpoint",
                hostname=hostname,
                detail={"reason": "not_configured"},
            )
        return EnforcementResult(
            success=False,
            provider=self.name,
            action="quarantine_endpoint",
            hostname=hostname,
            detail={"reason": "stub"},
        )

    async def available_for_endpoint(self, hostname: str) -> bool:
        if not self._configured():
            logger.warning("Intune integration not yet configured")
            return False
        return False
