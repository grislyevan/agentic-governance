"""Bridge between the GUI layer and the existing collector daemon loop.

Runs the scan pipeline in a background thread and exposes status
information to the menu bar / status window via callbacks.
"""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import platform
import socket
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config_loader import load_collector_config
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter
from agent.state import StateDiffer

logger = logging.getLogger(__name__)

STATUS_CONNECTED = "connected"
STATUS_DISCONNECTED = "disconnected"
STATUS_SCANNING = "scanning"
STATUS_ERROR = "error"
STATUS_STOPPED = "stopped"

StatusCallback = Callable[[str, dict[str, Any]], None]


class DaemonBridge:
    """Runs the collector scan loop in a background thread.

    The GUI thread polls ``status``, ``last_scan_time``, etc. or registers
    a callback via ``add_status_callback`` to receive push updates.
    """

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._scan_now_event = threading.Event()
        self._status = STATUS_DISCONNECTED
        self._last_scan_time: datetime | None = None
        self._events_sent = 0
        self._events_buffered = 0
        self._scan_count = 0
        self._error_message: str | None = None
        self._callbacks: list[StatusCallback] = []
        self._lock = threading.Lock()

    def add_status_callback(self, fn: StatusCallback) -> None:
        self._callbacks.append(fn)

    def _notify(self, status: str, **kwargs: Any) -> None:
        with self._lock:
            self._status = status
        for fn in self._callbacks:
            try:
                fn(status, kwargs)
            except Exception:
                logger.warning("Status callback raised an exception", exc_info=True)

    @property
    def status(self) -> str:
        with self._lock:
            return self._status

    @property
    def last_scan_time(self) -> datetime | None:
        with self._lock:
            return self._last_scan_time

    @property
    def events_sent(self) -> int:
        with self._lock:
            return self._events_sent

    @property
    def scan_count(self) -> int:
        with self._lock:
            return self._scan_count

    @property
    def error_message(self) -> str | None:
        with self._lock:
            return self._error_message

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: dict[str, Any] | None = None) -> None:
        """Start the daemon scan loop in a background thread."""
        if self.is_running:
            logger.warning("DaemonBridge: already running")
            return

        self._load_agent_env()
        merged = load_collector_config()
        if config:
            merged.update(config)

        if not merged.get("api_url") or not merged.get("api_key"):
            self._notify(STATUS_DISCONNECTED, reason="No API URL or key configured")
            logger.warning(
                "DaemonBridge: cannot start without api_url and api_key"
            )
            return

        if merged.get("interval", 0) <= 0:
            merged["interval"] = 300

        self._stop_event.clear()
        self._scan_now_event.clear()

        self._thread = threading.Thread(
            target=self._run,
            args=(merged,),
            daemon=True,
            name="detec-daemon",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the daemon to stop and wait for it to finish."""
        self._stop_event.set()
        self._scan_now_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._notify(STATUS_STOPPED)

    def request_scan(self) -> None:
        """Wake the daemon loop to run an immediate scan cycle."""
        self._scan_now_event.set()

    def _run(self, config: dict[str, Any]) -> None:
        """Daemon loop (runs in background thread)."""
        from main import run_scan, _build_lifecycle_event, _PID_DIR

        _PID_DIR.mkdir(parents=True, exist_ok=True)

        api_url = config["api_url"]
        api_key = config["api_key"]
        interval = config.get("interval", 300)
        hostname = config.get("endpoint_id", socket.gethostname())
        protocol = config.get("protocol", "http")
        gateway_host = config.get("gateway_host")
        gateway_port = config.get("gateway_port", 8001)

        args = argparse.Namespace(
            output=config.get("output", "./scan-results.ndjson"),
            endpoint_id=hostname,
            actor_id=config.get("actor_id", getpass.getuser()),
            sensitivity=config.get("sensitivity", "Tier0"),
            dry_run=config.get("dry_run", False),
            verbose=config.get("verbose", False),
            interval=interval,
            api_url=api_url,
            api_key=api_key,
            report_all=config.get("report_all", False),
            enforce=config.get("enforce", False),
        )

        try:
            if protocol == "tcp":
                if not gateway_host:
                    from urllib.parse import urlparse
                    parsed = urlparse(api_url)
                    gateway_host = parsed.hostname or "localhost"
                tls_enabled = api_url.startswith("https://") if api_url else False
                from main import EVENT_VERSION
                emitter = TcpEmitter(
                    gateway_host=gateway_host,
                    gateway_port=gateway_port,
                    api_key=api_key,
                    hostname=hostname,
                    agent_version=EVENT_VERSION,
                    tls=tls_enabled,
                )
            else:
                emitter = HttpEmitter(api_url=api_url, api_key=api_key)
            differ = StateDiffer(report_all=args.report_all)
        except Exception as exc:
            with self._lock:
                self._error_message = str(exc)
            self._notify(STATUS_ERROR, error=str(exc))
            return

        self._notify(STATUS_CONNECTED)

        hb_stop = threading.Event()
        hb_thread = threading.Thread(
            target=self._heartbeat_loop,
            args=(emitter, hostname, interval, hb_stop),
            daemon=True,
            name="heartbeat",
        )
        hb_thread.start()

        transport = f"tcp://{gateway_host}:{gateway_port}" if protocol == "tcp" else api_url
        logger.info(
            "DaemonBridge: started (interval=%ds, %s=%s)", interval, "transport" if protocol == "tcp" else "api", transport
        )

        try:
            while not self._stop_event.is_set():
                flushed = emitter.flush_buffer()
                if flushed:
                    logger.info("DaemonBridge: flushed %d buffered events", flushed)

                self._notify(STATUS_SCANNING)

                try:
                    run_scan(args, emitter=emitter, state_differ=differ)
                    with self._lock:
                        self._last_scan_time = datetime.now(timezone.utc)
                        self._scan_count += 1
                        stats = emitter.stats
                        self._events_sent = stats.get("sent", 0)
                        self._events_buffered = stats.get("buffered", 0)
                        self._error_message = None
                    self._notify(STATUS_CONNECTED)
                except Exception as exc:
                    logger.warning("DaemonBridge: scan failed: %s", exc, exc_info=True)
                    with self._lock:
                        self._error_message = str(exc)
                    self._notify(STATUS_ERROR, error=str(exc))

                # Wait for interval or until scan-now / stop is requested
                self._scan_now_event.clear()
                self._scan_now_event.wait(timeout=interval)
                if self._stop_event.is_set():
                    break
        finally:
            hb_stop.set()

            try:
                shutdown_event = _build_lifecycle_event(
                    event_type="agent.shutdown",
                    endpoint_id=hostname,
                    actor_id=args.actor_id,
                    summary="Collector agent shutting down gracefully",
                )
                emitter.emit(shutdown_event)
            except Exception:
                logger.warning("DaemonBridge: failed to emit shutdown event", exc_info=True)

            self._notify(STATUS_STOPPED)
            logger.info("DaemonBridge: stopped")

    @staticmethod
    def _load_agent_env() -> None:
        """Load agent.env written by ``detec-agent setup`` into os.environ.

        On macOS the file lives at ~/Library/Application Support/Detec/agent.env.
        Existing env vars are not overwritten.
        """
        if sys.platform == "darwin":
            env_file = Path.home() / "Library" / "Application Support" / "Detec" / "agent.env"
        elif sys.platform == "win32":
            env_file = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec" / "Agent" / "agent.env"
        else:
            env_file = Path.home() / ".local" / "share" / "detec" / "agent.env"

        if not env_file.exists():
            return
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value

    @staticmethod
    def _heartbeat_loop(
        emitter: HttpEmitter | TcpEmitter,
        hostname: str,
        interval: int,
        stop_event: threading.Event,
        telemetry_provider: str = "polling",
    ) -> None:
        while not stop_event.wait(timeout=interval):
            emitter.heartbeat(
                hostname=hostname,
                interval_seconds=interval,
                telemetry_provider=telemetry_provider,
            )
