"""TCP/binary transport for sending events to the central API.

Replaces HttpEmitter when running in daemon mode with ``--protocol tcp``.
Maintains a persistent connection to the DetecGateway, batches events,
tracks acknowledgements, and handles reconnection transparently.

The public API is synchronous to match HttpEmitter's interface. A background
thread runs an asyncio event loop that manages the TCP connection.
"""

from __future__ import annotations

import asyncio
import logging
import queue
import ssl
import threading
import time
from typing import Any, Callable

PostureCallback = Callable[[str, float | None, list[str] | None, list[str] | None], None]
IntervalCallback = Callable[[int], None]

from collector.agent.buffer import LocalBuffer

from protocol.wire import MessageType, FrameReader, encode_frame
from protocol.messages import (
    auth_msg,
    event_msg,
    event_batch_msg,
    heartbeat_msg,
)
from protocol.connection import BaseConnection

logger = logging.getLogger(__name__)

_BATCH_SIZE = 50
_BATCH_TIMEOUT = 1.0  # seconds
_RECONNECT_BASE = 1.0
_RECONNECT_MAX = 60.0
_BUFFER_FALLBACK_THRESHOLD = 300  # seconds disconnected before spilling to buffer


class _QueueItem:
    """Internal item placed on the send queue."""

    __slots__ = ("kind", "data", "result")

    def __init__(self, kind: str, data: Any) -> None:
        self.kind = kind
        self.data = data
        self.result: bool | None = None


class TcpEmitter:
    """Persistent binary-protocol emitter for daemon mode.

    Same interface as HttpEmitter: ``emit()``, ``heartbeat()``,
    ``flush_buffer()``, and ``stats``.
    """

    def __init__(
        self,
        gateway_host: str,
        gateway_port: int,
        api_key: str,
        hostname: str,
        agent_version: str = "0.0.0",
        buffer: LocalBuffer | None = None,
        tls: bool = False,
        tls_verify: bool = True,
        tls_ca: str | None = None,
        on_command: Callable[[str, str, dict], None] | None = None,
        on_policy: Callable[[list[dict]], None] | None = None,
        on_posture: PostureCallback | None = None,
        on_interval: IntervalCallback | None = None,
        failover_threshold: int | None = None,
        on_before_failover: Callable[[], None] | None = None,
        on_degraded: Callable[[], None] | None = None,
    ) -> None:
        self._host = gateway_host
        self._port = gateway_port
        self._api_key = api_key
        self._hostname = hostname
        self._agent_version = agent_version
        self._buffer = buffer or LocalBuffer()
        self._tls = tls
        self._tls_verify = tls_verify
        self._tls_ca = tls_ca

        self._on_command = on_command
        self._on_policy = on_policy
        self._on_posture = on_posture
        self._on_interval = on_interval
        self._failover_threshold = failover_threshold
        self._on_before_failover = on_before_failover
        self._on_degraded = on_degraded

        self._send_queue: queue.Queue[_QueueItem] = queue.Queue(maxsize=5000)
        self._sent = 0
        self._buffered = 0
        self._acked = 0
        self._nacked = 0

        self._connected = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    def _ensure_started(self) -> None:
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="tcp-emitter",
            daemon=True,
        )
        self._thread.start()

    # -- Public interface (synchronous, called from main thread) -------------

    def emit(self, event: dict[str, Any]) -> bool:
        """Send a single event. Returns True if queued, False if buffered."""
        self._ensure_started()
        item = _QueueItem("event", event)
        try:
            self._send_queue.put(item, timeout=5.0)
            return True
        except queue.Full:
            self._buffer.append(event)
            self._buffered += 1
            logger.warning("TcpEmitter: send queue full, event %s buffered", event.get("event_id", "?"))
            return False

    def heartbeat(
        self,
        hostname: str,
        interval_seconds: int = 0,
        telemetry_provider: str | None = None,
    ) -> bool:
        """Send a heartbeat."""
        self._ensure_started()
        data: dict[str, str | int] = {
            "hostname": hostname,
            "interval_seconds": interval_seconds,
        }
        if telemetry_provider:
            data["telemetry_provider"] = telemetry_provider
        item = _QueueItem("heartbeat", data)
        try:
            self._send_queue.put(item, timeout=2.0)
            return True
        except queue.Full:
            return False

    def flush_buffer(self) -> int:
        """Drain the local buffer and re-queue events for delivery."""
        events = self._buffer.drain()
        if not events:
            return 0
        flushed = 0
        for ev in events:
            if self.emit(ev):
                flushed += 1
        logger.info("TcpEmitter: re-queued %d/%d buffered events", flushed, len(events))
        return flushed

    @property
    def stats(self) -> dict[str, int]:
        return {
            "sent": self._sent,
            "buffered": self._buffered,
            "buffer_size": self._buffer.size(),
            "acked": self._acked,
            "nacked": self._nacked,
            "emitted": self._sent,
            "failed": self._buffered,
        }

    def shutdown(self) -> None:
        """Drain remaining events and stop the background thread."""
        self._stop.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10.0)

    # -- Background thread ---------------------------------------------------

    def _run_loop(self) -> None:
        """Entry point for the background IO thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connection_manager())
        except Exception:
            if not self._stop.is_set():
                logger.exception("TcpEmitter: background loop crashed")
        finally:
            try:
                self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            except Exception:
                pass
            self._loop.close()

    async def _connection_manager(self) -> None:
        """Reconnection loop: connect, authenticate, process queue, repeat."""
        backoff = _RECONNECT_BASE
        disconnect_since: float | None = None
        connect_fail_streak = 0

        while not self._stop.is_set():
            try:
                conn = await self._connect_and_auth()
                if conn is None:
                    connect_fail_streak += 1
                    self._connected.clear()
                    if disconnect_since is None:
                        disconnect_since = time.monotonic()
                    logger.warning(
                        "TcpEmitter: authentication failed (streak=%d)", connect_fail_streak
                    )
                    if self._should_failover(connect_fail_streak, disconnect_since):
                        await self._execute_failover()
                        return
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _RECONNECT_MAX)
                    continue

                self._connected.set()
                backoff = _RECONNECT_BASE
                disconnect_since = None
                connect_fail_streak = 0
                logger.info("TcpEmitter: connected to %s:%d", self._host, self._port)

                await self._process_queue(conn)
            except (ConnectionError, OSError, asyncio.TimeoutError) as exc:
                self._connected.clear()
                connect_fail_streak += 1
                if disconnect_since is None:
                    disconnect_since = time.monotonic()
                logger.warning(
                    "TcpEmitter: connection lost: %s (reconnecting in %.0fs, streak=%d)",
                    exc,
                    backoff,
                    connect_fail_streak,
                )
                if self._should_failover(connect_fail_streak, disconnect_since):
                    await self._execute_failover()
                    return
            except Exception:
                self._connected.clear()
                connect_fail_streak += 1
                if disconnect_since is None:
                    disconnect_since = time.monotonic()
                logger.exception(
                    "TcpEmitter: unexpected error (reconnecting in %.0fs, streak=%d)",
                    backoff,
                    connect_fail_streak,
                )
                if self._should_failover(connect_fail_streak, disconnect_since):
                    await self._execute_failover()
                    return

            if self._stop.is_set():
                break

            if disconnect_since and (time.monotonic() - disconnect_since) > _BUFFER_FALLBACK_THRESHOLD:
                self._spill_queue_to_buffer()

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _RECONNECT_MAX)

    def _should_failover(self, connect_fail_streak: int, disconnect_since: float | None) -> bool:
        if (
            self._failover_threshold is None
            or self._on_degraded is None
            or disconnect_since is None
        ):
            return False
        elapsed = time.monotonic() - disconnect_since
        return connect_fail_streak >= self._failover_threshold and elapsed >= 1.0

    async def _execute_failover(self) -> None:
        if self._on_before_failover:
            try:
                self._on_before_failover()
            except Exception:
                logger.exception("TcpEmitter: on_before_failover failed")
        self._spill_queue_to_buffer()
        if self._on_degraded:
            try:
                self._on_degraded()
            except Exception:
                logger.exception("TcpEmitter: on_degraded failed")
        self._stop.set()

    async def _connect_and_auth(self) -> _AgentConnection | None:
        """Open a TCP connection, optionally wrap in TLS, and authenticate."""
        ssl_ctx = None
        if self._tls:
            ssl_ctx = BaseConnection.make_client_ssl_context(
                cafile=self._tls_ca,
                verify=self._tls_verify,
            )

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port, ssl=ssl_ctx),
            timeout=10.0,
        )

        conn = _AgentConnection(
            reader, writer,
            label=f"agent:{self._hostname}",
            on_command=self._on_command,
            on_policy=self._on_policy,
            on_posture=self._on_posture,
        )

        msg = auth_msg(self._api_key, self._hostname, self._agent_version, seq=conn.next_seq())
        await conn.send(msg)

        resp = await asyncio.wait_for(conn.recv(), timeout=10.0)
        if resp is None:
            await conn.close()
            return None

        if resp.get("t") == MessageType.AUTH_OK:
            conn.session_id = resp["p"].get("session_id")
            conn.endpoint_id = resp["p"].get("endpoint_id")
            return conn

        reason = resp.get("p", {}).get("reason", "unknown")
        logger.error("TcpEmitter: auth rejected: %s", reason)
        await conn.close()
        return None

    async def _process_queue(self, conn: _AgentConnection) -> None:
        """Drain send queue and send events (batched) until disconnected."""
        reader_task = asyncio.create_task(self._reader_loop(conn))

        try:
            while not self._stop.is_set():
                batch: list[dict[str, Any]] = []
                deadline = time.monotonic() + _BATCH_TIMEOUT

                while len(batch) < _BATCH_SIZE and time.monotonic() < deadline:
                    remaining = max(0.01, deadline - time.monotonic())
                    item = await self._dequeue(timeout=remaining)
                    if item is None:
                        break

                    if item.kind == "heartbeat":
                        seq = conn.next_seq()
                        try:
                            await conn.send(heartbeat_msg(item.data, seq=seq))
                        except (ConnectionError, OSError):
                            return
                        continue

                    if item.kind == "event":
                        batch.append(item.data)

                if batch:
                    seq = conn.next_seq()
                    try:
                        if len(batch) == 1:
                            await conn.send(event_msg(batch[0], seq=seq))
                        else:
                            await conn.send(event_batch_msg(batch, seq=seq))
                    except (ConnectionError, OSError):
                        return
                    self._sent += len(batch)
        finally:
            reader_task.cancel()
            try:
                await reader_task
            except asyncio.CancelledError:
                pass
            await conn.close()

    async def _reader_loop(self, conn: _AgentConnection) -> None:
        """Background reader for ACK/NACK/push messages from server."""
        while True:
            try:
                msg = await conn.recv()
            except (ConnectionError, OSError):
                break
            if msg is None:
                break
            msg_type = msg.get("t")

            if msg_type == MessageType.ACK:
                count = len(msg.get("p", {}).get("seq_ids", []))
                self._acked += count

            elif msg_type == MessageType.NACK:
                failures = msg.get("p", {}).get("failures", [])
                self._nacked += len(failures)
                for f in failures:
                    logger.warning("TcpEmitter: NACK seq=%s: %s", f.get("seq_id"), f.get("reason"))

            elif msg_type == MessageType.HEARTBEAT_ACK:
                p = msg.get("p", {})
                logger.debug("TcpEmitter: heartbeat ack, status=%s", p.get("endpoint_status"))
                posture = p.get("enforcement_posture")
                if posture is not None and self._on_posture:
                    threshold = p.get("auto_enforce_threshold")
                    allow_list = p.get("allow_list")
                    llm_hosts = p.get("llm_hosts")
                    self._on_posture(
                        posture,
                        float(threshold) if threshold is not None else None,
                        allow_list if isinstance(allow_list, list) else None,
                        llm_hosts if isinstance(llm_hosts, list) else None,
                    )

            elif msg_type == MessageType.POSTURE_PUSH:
                p = msg.get("p", {})
                if self._on_posture:
                    posture = p.get("posture", "passive")
                    threshold = p.get("auto_enforce_threshold")
                    allow_list = p.get("allow_list")
                    llm_hosts = p.get("llm_hosts")
                    self._on_posture(
                        posture,
                        float(threshold) if threshold is not None else None,
                        allow_list if isinstance(allow_list, list) else None,
                        llm_hosts if isinstance(llm_hosts, list) else None,
                    )

            elif msg_type == MessageType.POLICY_PUSH:
                await conn.handle_message(msg)

            elif msg_type == MessageType.COMMAND:
                await conn.handle_message(msg)

            elif msg_type == MessageType.ERROR:
                p = msg.get("p", {})
                logger.error("TcpEmitter: server error %s: %s", p.get("code"), p.get("message"))

            else:
                logger.debug("TcpEmitter: unhandled message type 0x%02x", msg_type)

    async def _dequeue(self, timeout: float) -> _QueueItem | None:
        """Non-blocking dequeue with timeout, compatible with asyncio."""
        loop = asyncio.get_event_loop()
        try:
            return await asyncio.wait_for(
                loop.run_in_executor(None, self._send_queue.get, True, timeout),
                timeout=timeout + 0.5,
            )
        except (queue.Empty, asyncio.TimeoutError):
            return None

    def _spill_queue_to_buffer(self) -> None:
        """Move all queued events to the local buffer when disconnected too long."""
        spilled = 0
        while True:
            try:
                item = self._send_queue.get_nowait()
            except queue.Empty:
                break
            if item.kind == "event":
                self._buffer.append(item.data)
                self._buffered += 1
                spilled += 1
        if spilled:
            logger.info("TcpEmitter: spilled %d events to local buffer", spilled)


class _AgentConnection(BaseConnection):
    """Agent-side connection that handles server-pushed messages."""

    def __init__(
        self,
        reader,
        writer,
        *,
        label: str,
        on_command: Callable[[str, str, dict], None] | None = None,
        on_policy: Callable[[list[dict]], None] | None = None,
        on_posture: Callable | None = None,
        **kwargs,
    ) -> None:
        super().__init__(reader, writer, label=label, **kwargs)
        self.session_id: str | None = None
        self.endpoint_id: str | None = None
        self._on_command = on_command
        self._on_policy = on_policy
        self._on_posture = on_posture

    async def handle_message(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("t")

        if msg_type == MessageType.POLICY_PUSH:
            rules = msg.get("p", {}).get("rules", [])
            logger.info("Received policy push with %d rules", len(rules))
            if self._on_policy:
                self._on_policy(rules)

        elif msg_type == MessageType.POSTURE_PUSH:
            p = msg.get("p", {})
            logger.info("Received posture push: %s", p.get("posture"))
            if self._on_posture:
                posture = p.get("posture", "passive")
                threshold = p.get("auto_enforce_threshold")
                allow_list = p.get("allow_list")
                llm_hosts = p.get("llm_hosts")
                self._on_posture(
                    posture,
                    float(threshold) if threshold is not None else None,
                    allow_list if isinstance(allow_list, list) else None,
                    llm_hosts if isinstance(llm_hosts, list) else None,
                )

        elif msg_type == MessageType.COMMAND:
            payload = msg.get("p", {})
            command = payload.get("command", "")
            command_id = payload.get("command_id", "")
            params = payload.get("params", {})
            logger.info("Received command: %s (id=%s)", command, command_id)
            if self._on_command:
                self._on_command(command, command_id, params)

            from protocol.messages import command_ack_msg
            try:
                await self.send(command_ack_msg(command_id, "received", seq=self.next_seq()))
            except ConnectionError:
                pass


def try_tcp_auth(
    gateway_host: str,
    gateway_port: int,
    api_key: str,
    hostname: str,
    agent_version: str,
    *,
    tls: bool = False,
    tls_verify: bool = True,
    tls_ca: str | None = None,
    timeout: float = 3.0,
) -> tuple[bool, str]:
    """Try one TCP connect + auth. Returns (ok, error_reason). Sync; uses asyncio.run."""

    async def _attempt() -> tuple[bool, str]:
        ssl_ctx = None
        if tls:
            ssl_ctx = BaseConnection.make_client_ssl_context(
                cafile=tls_ca,
                verify=tls_verify,
            )
        per = min(10.0, max(0.5, timeout))
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(gateway_host, gateway_port, ssl=ssl_ctx),
            timeout=per,
        )
        conn = _AgentConnection(
            reader,
            writer,
            label=f"probe:{hostname}",
            on_command=None,
            on_policy=None,
            on_posture=None,
        )
        try:
            msg = auth_msg(api_key, hostname, agent_version, seq=conn.next_seq())
            await conn.send(msg)
            resp = await asyncio.wait_for(conn.recv(), timeout=per)
            if resp is not None and resp.get("t") == MessageType.AUTH_OK:
                return True, ""
            reason = "auth_failed"
            if isinstance(resp, dict):
                reason = str(resp.get("p", {}).get("reason", reason))
            return False, reason
        finally:
            await conn.close()

    try:
        return asyncio.run(asyncio.wait_for(_attempt(), timeout=timeout))
    except asyncio.TimeoutError:
        return False, "timeout"
    except OSError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)
