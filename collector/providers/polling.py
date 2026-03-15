"""Polling-based telemetry provider using psutil."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import psutil

from telemetry.event_store import (
    FileChangeEvent,
    NetworkConnectEvent,
    ProcessExecEvent,
)

from .base import TelemetryProvider

if TYPE_CHECKING:
    from telemetry.event_store import EventStore

logger = logging.getLogger(__name__)


def _gather_process_snapshot() -> list[ProcessExecEvent]:
    """Lightweight process snapshot for probe loop."""
    now = datetime.now(timezone.utc)
    out: list[ProcessExecEvent] = []
    try:
        for proc in psutil.process_iter(["pid", "name", "cmdline", "username", "ppid"]):
            try:
                info = proc.info
                pname: str = info.get("name") or ""
                cmdline_parts: list = info.get("cmdline") or []
                cmdline = " ".join(str(p) for p in cmdline_parts)
                out.append(
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
    return out


def _gather_network_snapshot() -> list[NetworkConnectEvent]:
    """Lightweight network snapshot for probe loop."""
    now = datetime.now(timezone.utc)
    out: list[NetworkConnectEvent] = []
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
            out.append(
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
    return out


class PollingProvider(TelemetryProvider):
    """Telemetry provider that polls psutil for process and network snapshots.

    When start() is called with sink and probe_interval_ms (sentinel mode),
    a background thread runs a lightweight probe loop that emits ProbeDeltas
    to the sink. poll() continues to fill the store for full scan cycles.
    """

    @property
    def name(self) -> str:
        return "polling"

    def __init__(self) -> None:
        self._store: EventStore | None = None
        self._probe_thread: threading.Thread | None = None
        self._probe_stop: threading.Event | None = None
        self._prev_process: list[ProcessExecEvent] = []
        self._prev_network: list[NetworkConnectEvent] = []
        self._prev_file: list[FileChangeEvent] = []

    def available(self) -> bool:
        return True

    def start(
        self,
        store: EventStore,
        *,
        sink: Any = None,
        probe_interval_ms: int | None = None,
    ) -> None:
        self._store = store
        if sink is not None and probe_interval_ms is not None and probe_interval_ms > 0:
            from probe.delta import build_probe_delta

            self._probe_stop = threading.Event()
            interval_sec = probe_interval_ms / 1000.0

            def _probe_loop() -> None:
                while not self._probe_stop.wait(timeout=interval_sec):
                    try:
                        now = datetime.now(timezone.utc)
                        cur_p = _gather_process_snapshot()
                        cur_n = _gather_network_snapshot()
                        cur_f: list[FileChangeEvent] = []
                        delta = build_probe_delta(
                            now,
                            "polling",
                            cur_p,
                            cur_n,
                            cur_f,
                            self._prev_process,
                            self._prev_network,
                            self._prev_file,
                        )
                        self._prev_process = cur_p
                        self._prev_network = cur_n
                        self._prev_file = cur_f
                        if (
                            delta.process_events
                            or delta.network_events
                            or delta.file_events
                        ):
                            sink.push_delta(delta)
                    except Exception:
                        logger.debug("Probe loop iteration failed", exc_info=True)

            self._probe_thread = threading.Thread(
                target=_probe_loop,
                daemon=True,
                name="probe-loop",
            )
            self._probe_thread.start()
            logger.debug("Probe loop started (interval_ms=%s)", probe_interval_ms)

    def stop(self) -> None:
        if self._probe_stop is not None:
            self._probe_stop.set()
        if self._probe_thread is not None:
            self._probe_thread.join(timeout=2.0)
            self._probe_thread = None
        self._probe_stop = None
        self._store = None
        self._prev_process = []
        self._prev_network = []
        self._prev_file = []

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
