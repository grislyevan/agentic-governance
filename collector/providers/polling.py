"""Polling-based telemetry provider using psutil."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import psutil

from telemetry.event_store import (
    NetworkConnectEvent,
    ProcessExecEvent,
)

from .base import TelemetryProvider

if TYPE_CHECKING:
    from telemetry.event_store import EventStore


class PollingProvider(TelemetryProvider):
    """Telemetry provider that polls psutil for process and network snapshots."""

    @property
    def name(self) -> str:
        return "polling"

    def __init__(self) -> None:
        self._store: EventStore | None = None

    def available(self) -> bool:
        return True

    def start(self, store: EventStore) -> None:
        self._store = store

    def stop(self) -> None:
        self._store = None

    def poll(self) -> None:
        """Poll psutil and push events into the store. Call on each scan cycle."""
        if self._store is None:
            return

        now = datetime.now(timezone.utc)

        # Process events from psutil.process_iter()
        try:
            for proc in psutil.process_iter(["pid", "name", "cmdline", "username", "ppid"]):
                try:
                    info = proc.info
                    pname: str = info.get("name") or ""
                    cmdline_parts: list = info.get("cmdline") or []
                    cmdline = " ".join(str(p) for p in cmdline_parts)

                    self._store.push_process(
                        ProcessExecEvent(
                            timestamp=now,
                            pid=info["pid"],
                            ppid=info.get("ppid") or 0,
                            name=pname,
                            cmdline=cmdline,
                            username=info.get("username"),
                            binary_path=None,
                            source="polling",
                        )
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except (psutil.AccessDenied, psutil.Error):
            pass

        # Network events from psutil.net_connections()
        try:
            for conn in psutil.net_connections(kind="tcp"):
                laddr = conn.laddr
                raddr = conn.raddr
                local_port = laddr.port if laddr else 0
                remote_addr = raddr.ip if raddr else ""
                remote_port = raddr.port if raddr else 0

                process_name = ""
                if conn.pid is not None:
                    try:
                        p = psutil.Process(conn.pid)
                        process_name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

                self._store.push_network(
                    NetworkConnectEvent(
                        timestamp=now,
                        pid=conn.pid or 0,
                        process_name=process_name,
                        remote_addr=remote_addr or "",
                        remote_port=remote_port,
                        local_port=local_port,
                        protocol="tcp",
                        sni=None,
                        source="polling",
                    )
                )
        except psutil.AccessDenied:
            pass
