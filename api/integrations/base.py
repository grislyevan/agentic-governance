"""EDR provider interface for telemetry enrichment."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from .types import ProcessExecEvent, NetworkConnectEvent, FileChangeEvent


class EDRProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def query_process_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[ProcessExecEvent]: ...

    @abstractmethod
    async def query_network_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[NetworkConnectEvent]: ...

    @abstractmethod
    async def query_file_events(
        self, endpoint_id: str, start: datetime, end: datetime
    ) -> list[FileChangeEvent]: ...

    @abstractmethod
    async def resolve_endpoint_id(
        self, hostname: str, mac_address: str | None = None
    ) -> str | None: ...
