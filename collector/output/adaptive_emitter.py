"""TCP-first transport with HTTP fallback and optional TCP recovery (protocol auto)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable

from agent.buffer import LocalBuffer
from output.http_emitter import HttpEmitter
from output.tcp_emitter import TcpEmitter, try_tcp_auth

log = logging.getLogger("transport")

PostureCb = Callable[[str, float | None, list[str] | None, list[str] | None], None]
RestoreCb = Callable[[list[str]], None]
IntervalCb = Callable[[int], None]
CommandCb = Callable[[str, str, dict], None]


class AdaptiveEmitter:
    """Single emit/heartbeat/flush surface; at most one of TCP or HTTP sends."""

    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        hostname: str,
        agent_version: str,
        gateway_host: str,
        gateway_port: int,
        tls: bool,
        tcp_connect_timeout: float = 3.0,
        tcp_retry_interval: float = 30.0,
        tcp_failure_threshold: int = 5,
        tcp_recovery_stability: float = 10.0,
        on_posture: PostureCb | None = None,
        on_restore: RestoreCb | None = None,
        on_interval: IntervalCb | None = None,
        on_command: CommandCb | None = None,
        sign_events: bool = True,
    ) -> None:
        self._lock = threading.RLock()
        self._api_url = api_url
        self._api_key = api_key
        self._hostname = hostname
        self._agent_version = agent_version
        self._gateway_host = gateway_host
        self._gateway_port = gateway_port
        self._tls = tls
        self._tcp_connect_timeout = tcp_connect_timeout
        self._tcp_retry_interval = tcp_retry_interval
        self._tcp_failure_threshold = tcp_failure_threshold
        self._tcp_recovery_stability = tcp_recovery_stability
        self._on_posture = on_posture
        self._on_restore = on_restore
        self._on_interval = on_interval
        self._on_command = on_command

        self._shared_buffer = LocalBuffer()
        self._http = HttpEmitter(
            api_url=api_url,
            api_key=api_key,
            buffer=self._shared_buffer,
            sign_events=sign_events,
            on_posture=on_posture,
            on_restore=on_restore,
            on_interval=on_interval,
        )
        self._tcp: TcpEmitter | None = None
        self._prefer_http = False
        self._recovery_stop = threading.Event()
        self._recovery_thread: threading.Thread | None = None

        log.info("[transport] mode=auto startup: attempting tcp")
        ok, reason = try_tcp_auth(
            gateway_host,
            gateway_port,
            api_key,
            hostname,
            agent_version,
            tls=tls,
            timeout=tcp_connect_timeout,
        )
        if ok:
            self._tcp = self._spawn_tcp_emitter()
            log.info("[transport] tcp connected")
        else:
            self._prefer_http = True
            log.warning(
                "[transport] tcp unavailable (%s), switching to http fallback", reason
            )
            log.info("[transport] http fallback active")

        self._recovery_thread = threading.Thread(
            target=self._recovery_worker,
            name="transport-recovery",
            daemon=True,
        )
        self._recovery_thread.start()

    def _spawn_tcp_emitter(self) -> TcpEmitter:
        def _before() -> None:
            self._prefer_http = True

        def _degraded() -> None:
            log.warning("[transport] tcp unavailable, switching to http fallback")
            log.info("[transport] http fallback active")
            log.info("[transport] transport switch complete")
            with self._lock:
                self._tcp = None

        return TcpEmitter(
            gateway_host=self._gateway_host,
            gateway_port=self._gateway_port,
            api_key=self._api_key,
            hostname=self._hostname,
            agent_version=self._agent_version,
            buffer=self._shared_buffer,
            tls=self._tls,
            on_posture=self._on_posture,
            on_command=self._on_command,
            failover_threshold=self._tcp_failure_threshold,
            on_before_failover=_before,
            on_degraded=_degraded,
        )

    def _recovery_worker(self) -> None:
        while not self._recovery_stop.wait(timeout=self._tcp_retry_interval):
            with self._lock:
                if not self._prefer_http:
                    continue
                if self._tcp is not None:
                    continue
            log.debug("[transport] probing tcp...")
            ok, _ = try_tcp_auth(
                self._gateway_host,
                self._gateway_port,
                self._api_key,
                self._hostname,
                self._agent_version,
                tls=self._tls,
                timeout=self._tcp_connect_timeout,
            )
            if not ok:
                continue
            time.sleep(self._tcp_recovery_stability)
            ok2, _ = try_tcp_auth(
                self._gateway_host,
                self._gateway_port,
                self._api_key,
                self._hostname,
                self._agent_version,
                tls=self._tls,
                timeout=self._tcp_connect_timeout,
            )
            if not ok2:
                continue
            with self._lock:
                if self._recovery_stop.is_set():
                    return
                if self._tcp is not None:
                    continue
                log.info("[transport] tcp recovered, switching back")
                self._prefer_http = False
                self._tcp = self._spawn_tcp_emitter()
            try:
                self.flush_buffer()
            except Exception:
                log.exception("[transport] flush after tcp recovery")
            log.info("[transport] transport switch complete")

    def uses_http_heartbeat(self) -> bool:
        with self._lock:
            return self._prefer_http or self._tcp is None

    def emit(self, event: dict[str, Any]) -> bool:
        with self._lock:
            prefer_http = self._prefer_http
            tcp = self._tcp
        if not prefer_http and tcp is not None:
            return tcp.emit(event)
        return self._http.emit(event)

    def heartbeat(self, **kwargs: Any) -> bool:
        with self._lock:
            prefer_http = self._prefer_http
            tcp = self._tcp
        if not prefer_http and tcp is not None:
            return tcp.heartbeat(**kwargs)
        return self._http.heartbeat(**kwargs)

    def flush_buffer(self) -> int:
        with self._lock:
            prefer_http = self._prefer_http
            tcp = self._tcp
        total = 0
        if not prefer_http and tcp is not None:
            total += tcp.flush_buffer()
        total += self._http.flush_buffer()
        return total

    @property
    def stats(self) -> dict[str, Any]:
        with self._lock:
            prefer_http = self._prefer_http
            tcp = self._tcp
        out: dict[str, Any] = {
            "transport": "http" if (prefer_http or tcp is None) else "tcp",
            "prefer_http": prefer_http,
        }
        if tcp is not None:
            out.update(tcp.stats)
        else:
            out.update(self._http.stats)
        return out

    def shutdown(self) -> None:
        self._recovery_stop.set()
        if self._recovery_thread and self._recovery_thread.is_alive():
            self._recovery_thread.join(timeout=2.0)
        with self._lock:
            t = self._tcp
            self._tcp = None
        if t is not None:
            t.shutdown()
