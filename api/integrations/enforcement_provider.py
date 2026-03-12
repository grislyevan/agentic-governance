"""Enforcement provider interface for delegated EDR/MDM enforcement.

Separate from EDRProvider (base.py), which queries telemetry for enrichment.
EnforcementProvider sends enforcement commands (kill, contain, quarantine)
to external tools like CrowdStrike RTR, SentinelOne, etc.

A single EDR product can implement both interfaces, but they stay separate
so enrichment-only and enforcement-only deployments are both supported.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class EnforcementResult:
    """Outcome of an enforcement action attempt."""

    success: bool
    provider: str
    action: str
    hostname: str
    detail: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def summary(self) -> str:
        status = "succeeded" if self.success else "failed"
        return f"{self.provider}:{self.action} on {self.hostname} {status}"


class EnforcementProvider(ABC):
    """Abstract interface for delegated enforcement via EDR/MDM tools.

    Implementations translate generic enforcement intents into
    vendor-specific API calls (CrowdStrike RTR, SentinelOne Remote Script,
    Intune remediation, etc.).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this provider (e.g. 'crowdstrike')."""
        ...

    @abstractmethod
    async def kill_process(
        self, hostname: str, pid: int, process_name: str
    ) -> EnforcementResult:
        """Kill a specific process on the target host.

        Returns an EnforcementResult indicating success or failure.
        Implementations should handle authentication, session management,
        and cleanup internally.
        """
        ...

    @abstractmethod
    async def block_network(self, hostname: str) -> EnforcementResult:
        """Network-isolate (contain) the target host.

        The host retains connectivity to the EDR cloud but loses all
        other network access. This is the EDR equivalent of quarantine.
        """
        ...

    @abstractmethod
    async def quarantine_endpoint(self, hostname: str) -> EnforcementResult:
        """Quarantine the target endpoint.

        For most EDR vendors this is equivalent to network containment.
        Providers may add additional restrictions (disable USB, etc.)
        if the vendor supports them.
        """
        ...

    @abstractmethod
    async def available_for_endpoint(self, hostname: str) -> bool:
        """Check whether this provider can enforce on the given host.

        Returns True if the host is found, managed, and the provider
        has the permissions/connectivity to issue enforcement commands.
        """
        ...
