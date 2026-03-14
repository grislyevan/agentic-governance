"""DetecGateway: binary protocol TCP/TLS server for agent connections.

Runs as an asyncio task in the same process as FastAPI, sharing the
event loop started by uvicorn.  Agents authenticate with their API key,
then send events and heartbeats over a persistent connection.  The
server can push policy updates and commands back to connected agents.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from core.config import settings
from core.metrics import detec_active_connections, detec_events_ingested_total
from core.database import SessionLocal
from core.event_validator import validate_event_payload
from models.allow_list import AllowListEntry
from models.endpoint import Endpoint, ENDPOINT_STATUS_ACTIVE
from models.event import Event
from models.tenant import Tenant
from models.user import User, verify_api_key, API_KEY_PREFIX_LEN
from core.audit_logger import record as _audit_record
from webhooks.dispatcher import dispatch_event as _dispatch_webhooks

from protocol import __version__ as PROTOCOL_VERSION
from protocol.connection import BaseConnection
from protocol.wire import MessageType
from protocol.messages import (
    auth_ok_msg,
    auth_fail_msg,
    ack_msg,
    nack_msg,
    heartbeat_ack_msg,
    posture_push_msg,
    error_msg,
)

logger = logging.getLogger(__name__)


class SessionRegistry:
    """Thread-safe registry of active agent sessions keyed by endpoint_id."""

    def __init__(self) -> None:
        self._sessions: dict[str, "AgentSession"] = {}
        self._lock = asyncio.Lock()

    async def register(self, endpoint_id: str, session: "AgentSession") -> None:
        async with self._lock:
            existing = self._sessions.get(endpoint_id)
            if existing and not existing.closed:
                logger.info("Evicting stale session for endpoint %s", endpoint_id)
                await existing.close()
            self._sessions[endpoint_id] = session

    async def unregister(self, endpoint_id: str) -> None:
        async with self._lock:
            self._sessions.pop(endpoint_id, None)

    async def get(self, endpoint_id: str) -> "AgentSession | None":
        async with self._lock:
            session = self._sessions.get(endpoint_id)
            if session and session.closed:
                del self._sessions[endpoint_id]
                return None
            return session

    async def all_sessions(self) -> list["AgentSession"]:
        async with self._lock:
            alive = {k: v for k, v in self._sessions.items() if not v.closed}
            self._sessions = alive
            return list(alive.values())

    @property
    def count(self) -> int:
        return len(self._sessions)


class AgentSession(BaseConnection):
    """Per-connection state for an authenticated agent."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        registry: SessionRegistry,
        read_timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        super().__init__(reader, writer, **kwargs)
        self._registry = registry
        self._read_timeout = read_timeout
        self._authenticated = False
        self._tenant_id: str | None = None
        self._endpoint_id: str | None = None
        self._hostname: str | None = None
        self._session_id = str(uuid.uuid4())
        self._agent_version: str | None = None

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    @property
    def endpoint_id(self) -> str | None:
        return self._endpoint_id

    @property
    def tenant_id(self) -> str | None:
        return self._tenant_id

    @property
    def session_id(self) -> str:
        return self._session_id

    async def handle_message(self, msg: dict[str, Any]) -> None:
        msg_type = msg.get("t")

        if not self._authenticated:
            if msg_type == MessageType.AUTH:
                await self._handle_auth(msg)
            else:
                await self.send(auth_fail_msg("Must authenticate first"))
                await self.close()
            return

        handlers = {
            MessageType.EVENT: self._handle_event,
            MessageType.EVENT_BATCH: self._handle_event_batch,
            MessageType.HEARTBEAT: self._handle_heartbeat,
            MessageType.COMMAND_ACK: self._handle_command_ack,
        }
        handler = handlers.get(msg_type)
        if handler:
            await handler(msg)
        else:
            logger.warning("AgentSession %s: unknown message type 0x%02x", self._session_id, msg_type)
            await self.send(error_msg(400, f"Unknown message type: {msg_type}"))

    async def _read_loop(self) -> None:
        """Override to add a per-recv timeout so idle connections are evicted."""
        while not self._closed:
            try:
                msg = await asyncio.wait_for(self.recv(), timeout=self._read_timeout)
            except asyncio.TimeoutError:
                logger.info(
                    "Session %s idle for %ds, closing",
                    self._session_id, self._read_timeout,
                )
                break
            if msg is None:
                logger.info("%s: remote end closed", self._label)
                break
            try:
                await self.handle_message(msg)
            except Exception:
                logger.exception(
                    "%s: error handling message type 0x%02x",
                    self._label, msg.get("t", 0),
                )

    # -- Authentication ------------------------------------------------------

    async def _handle_auth(self, msg: dict[str, Any]) -> None:
        payload = msg.get("p")
        if not isinstance(payload, dict):
            await self.send(auth_fail_msg("Invalid auth payload"))
            await self.close()
            return
        api_key = payload.get("api_key", "")
        hostname = payload.get("hostname", "")
        agent_version = payload.get("agent_version", "")

        if not api_key or not hostname:
            await self.send(auth_fail_msg("Missing api_key or hostname"))
            await self.close()
            return

        db = SessionLocal()
        try:
            tenant_id = self._verify_api_key(api_key, db)
            if not tenant_id:
                await self.send(auth_fail_msg("Invalid API key"))
                await self.close()
                return

            endpoint_id = self._get_or_create_endpoint(tenant_id, hostname, db)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Auth error for hostname %s", hostname)
            await self.send(auth_fail_msg("Internal authentication error"))
            await self.close()
            return
        finally:
            db.close()

        self._authenticated = True
        self._tenant_id = tenant_id
        self._endpoint_id = endpoint_id
        self._hostname = hostname
        self._agent_version = agent_version
        self._label = f"agent:{hostname}"

        await self._registry.register(endpoint_id, self)
        detec_active_connections.inc()

        await self.send(auth_ok_msg(
            session_id=self._session_id,
            endpoint_id=endpoint_id,
            server_version=PROTOCOL_VERSION,
        ))
        logger.info(
            "Agent authenticated: %s (endpoint=%s, agent_version=%s)",
            hostname, endpoint_id, agent_version,
        )

    @staticmethod
    def _verify_api_key(api_key: str, db) -> str | None:
        """Verify an API key (user prefix+hash or tenant agent key) and return the tenant_id, or None."""
        if len(api_key) >= API_KEY_PREFIX_LEN:
            prefix = api_key[:API_KEY_PREFIX_LEN]
            candidates = (
                db.query(User)
                .filter(User.api_key_prefix == prefix, User.is_active.is_(True))
                .all()
            )
            for user in candidates:
                if user.api_key_hash and verify_api_key(api_key, user.api_key_hash):
                    return user.tenant_id
        tenant = db.query(Tenant).filter(Tenant.agent_key == api_key).first()
        if tenant:
            return tenant.id
        return None

    @staticmethod
    def _get_or_create_endpoint(tenant_id: str, hostname: str, db) -> str:
        """Find or create an endpoint row, return its ID."""
        ep = db.query(Endpoint).filter(
            Endpoint.tenant_id == tenant_id,
            Endpoint.hostname == hostname,
        ).first()
        if not ep:
            ep = Endpoint(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                hostname=hostname,
                management_state="unmanaged",
                status=ENDPOINT_STATUS_ACTIVE,
                last_seen_at=datetime.now(timezone.utc),
            )
            db.add(ep)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                ep = db.query(Endpoint).filter(
                    Endpoint.tenant_id == tenant_id,
                    Endpoint.hostname == hostname,
                ).first()
        return ep.id

    # -- Event ingestion -----------------------------------------------------

    async def _handle_event(self, msg: dict[str, Any]) -> None:
        seq_id = msg.get("id", 0)
        event_data = msg.get("p", {})
        result = await asyncio.to_thread(self._ingest_event, event_data)
        if result:
            await self.send(ack_msg([seq_id]))
        else:
            await self.send(nack_msg([{"seq_id": seq_id, "reason": "ingestion failed"}]))

    async def _handle_event_batch(self, msg: dict[str, Any]) -> None:
        seq_id = msg.get("id", 0)
        events = msg.get("p", [])
        if not isinstance(events, list):
            await self.send(nack_msg([{"seq_id": seq_id, "reason": "batch payload must be array"}]))
            return

        acked: list[int] = []
        failed: list[dict[str, Any]] = []

        for i, event_data in enumerate(events):
            ok = await asyncio.to_thread(self._ingest_event, event_data)
            if ok:
                acked.append(seq_id)
            else:
                failed.append({"seq_id": seq_id, "reason": f"event[{i}] ingestion failed"})

        if acked:
            await self.send(ack_msg(acked))
        if failed:
            await self.send(nack_msg(failed))

    def _ingest_event(self, event_data: dict[str, Any]) -> bool:
        """Persist a single event to the database. Runs in a thread."""
        validation_errors = validate_event_payload(event_data)
        if validation_errors:
            logger.warning(
                "Event from %s failed validation: %s",
                self._hostname, "; ".join(validation_errors),
            )
            return False

        db = SessionLocal()
        try:
            event_id = event_data.get("event_id")
            if not event_id:
                logger.warning("Event missing event_id from %s", self._hostname)
                return False

            existing = db.query(Event).filter(
                Event.event_id == event_id,
                Event.tenant_id == self._tenant_id,
            ).first()
            if existing:
                return True

            tool = event_data.get("tool", {})
            policy = event_data.get("policy", {})
            severity = event_data.get("severity", {})
            endpoint_block = event_data.get("endpoint", {})

            attribution_sources = tool.get("attribution_sources")
            if isinstance(attribution_sources, list):
                attribution_sources = ",".join(attribution_sources)

            observed_at = event_data.get("observed_at")
            if isinstance(observed_at, str):
                observed_at = datetime.fromisoformat(observed_at)
            elif not isinstance(observed_at, datetime):
                observed_at = datetime.now(timezone.utc)

            event = Event(
                id=str(uuid.uuid4()),
                event_id=event_id,
                tenant_id=self._tenant_id,
                endpoint_id=self._endpoint_id,
                event_type=event_data.get("event_type", "unknown"),
                event_version=event_data.get("event_version", "1.0.0"),
                observed_at=observed_at,
                session_id=event_data.get("session_id"),
                trace_id=event_data.get("trace_id"),
                parent_event_id=event_data.get("parent_event_id"),
                tool_name=tool.get("name"),
                tool_class=tool.get("class"),
                tool_version=tool.get("version"),
                attribution_confidence=tool.get("attribution_confidence"),
                attribution_sources=attribution_sources,
                decision_state=policy.get("decision_state"),
                rule_id=policy.get("rule_id"),
                severity_level=severity.get("level"),
                payload=event_data,
            )
            db.add(event)
            db.commit()
            detec_events_ingested_total.inc()

            event_type_val = event_data.get("event_type", "")
            if event_type_val.startswith("enforcement.") or event_type_val == "posture.changed":
                enf_detail: dict[str, Any] = {}
                if event_data.get("enforcement"):
                    enf_detail["enforcement"] = event_data["enforcement"]
                if event_data.get("posture"):
                    enf_detail["posture"] = event_data["posture"]
                _audit_record(
                    db,
                    tenant_id=self._tenant_id,
                    actor_id=None,
                    actor_type="agent",
                    action=event_type_val,
                    resource_type="endpoint",
                    resource_id=self._endpoint_id,
                    detail=enf_detail if enf_detail else None,
                )

            try:
                _dispatch_webhooks(db, self._tenant_id, event_data)
            except Exception:
                logger.warning("Webhook dispatch failed for event %s", event_id, exc_info=True)

            return True
        except IntegrityError:
            db.rollback()
            return True
        except Exception:
            db.rollback()
            logger.exception("Failed to ingest event from %s", self._hostname)
            return False
        finally:
            db.close()

    # -- Heartbeat -----------------------------------------------------------

    async def _handle_heartbeat(self, msg: dict[str, Any]) -> None:
        seq_id = msg.get("id", 0)
        posture_info = await asyncio.to_thread(self._update_heartbeat)
        next_expected = (
            posture_info.get("interval_seconds")
            if posture_info and posture_info.get("interval_seconds") is not None
            else settings.default_heartbeat_interval
        )
        ack = heartbeat_ack_msg(
            next_expected_in=next_expected,
            endpoint_status=ENDPOINT_STATUS_ACTIVE,
            seq=seq_id,
        )
        if posture_info:
            ack["p"]["enforcement_posture"] = posture_info.get("enforcement_posture", "passive")
            ack["p"]["auto_enforce_threshold"] = posture_info.get("auto_enforce_threshold", 0.75)
            if "allow_list" in posture_info:
                ack["p"]["allow_list"] = posture_info["allow_list"]
            if posture_info.get("interval_seconds") is not None:
                ack["p"]["interval_seconds"] = posture_info["interval_seconds"]
        await self.send(ack)

    def _update_heartbeat(self) -> dict[str, Any] | None:
        """Touch the endpoint's last_seen_at and return posture/interval info. Runs in a thread.

        When the endpoint has a profile, returns profile's scan_interval_seconds so TCP agents
        receive server-pushed interval like HTTP heartbeat does.
        """
        db = SessionLocal()
        try:
            from sqlalchemy.orm import joinedload
            ep = (
                db.query(Endpoint)
                .options(joinedload(Endpoint.endpoint_profile))
                .filter(Endpoint.id == self._endpoint_id)
                .first()
            )
            if ep:
                ep.last_seen_at = datetime.now(timezone.utc)
                ep.status = ENDPOINT_STATUS_ACTIVE
                db.commit()
                allow_list = [
                    e.pattern for e in db.query(AllowListEntry).filter(AllowListEntry.tenant_id == ep.tenant_id).all()
                ]
                out = {
                    "enforcement_posture": ep.enforcement_posture,
                    "auto_enforce_threshold": ep.auto_enforce_threshold,
                    "allow_list": allow_list,
                }
                if ep.endpoint_profile is not None:
                    out["interval_seconds"] = ep.endpoint_profile.scan_interval_seconds
                return out
            return None
        except Exception:
            db.rollback()
            logger.warning("Heartbeat update failed for %s", self._endpoint_id, exc_info=True)
            return None
        finally:
            db.close()

    # -- Command acknowledgement ---------------------------------------------

    async def _handle_command_ack(self, msg: dict[str, Any]) -> None:
        payload = msg.get("p", {})
        logger.info(
            "Command ack from %s: command_id=%s result=%s",
            self._hostname,
            payload.get("command_id"),
            payload.get("result"),
        )

    # -- Cleanup -------------------------------------------------------------

    async def close(self) -> None:
        if self._endpoint_id:
            await self._registry.unregister(self._endpoint_id)
            detec_active_connections.dec()
        await super().close()
        logger.info("Session closed: %s (endpoint=%s)", self._hostname or "unauthenticated", self._endpoint_id)


_MAX_GLOBAL_CONNECTIONS = 500
_MAX_CONNECTIONS_PER_IP = 20
_READ_TIMEOUT = 120  # seconds; idle connections closed after this


class DetecGateway:
    """Asyncio TCP/TLS server that accepts binary protocol agent connections."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8001,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl_context = ssl_context
        self._server: asyncio.Server | None = None
        self._registry = SessionRegistry()
        self._active_connections = 0
        self._connections_per_ip: dict[str, int] = {}
        self._conn_lock = asyncio.Lock()

    @property
    def registry(self) -> SessionRegistry:
        return self._registry

    async def _track_connect(self, ip: str) -> bool:
        """Register a connection. Returns False if limits are exceeded."""
        async with self._conn_lock:
            if self._active_connections >= _MAX_GLOBAL_CONNECTIONS:
                return False
            current = self._connections_per_ip.get(ip, 0)
            if current >= _MAX_CONNECTIONS_PER_IP:
                return False
            self._active_connections += 1
            self._connections_per_ip[ip] = current + 1
            return True

    async def _track_disconnect(self, ip: str) -> None:
        async with self._conn_lock:
            self._active_connections = max(0, self._active_connections - 1)
            current = self._connections_per_ip.get(ip, 1)
            if current <= 1:
                self._connections_per_ip.pop(ip, None)
            else:
                self._connections_per_ip[ip] = current - 1

    async def serve(self) -> None:
        """Start listening for agent connections. Runs until cancelled."""
        self._server = await asyncio.start_server(
            self._handle_connection,
            self._host,
            self._port,
            ssl=self._ssl_context,
        )

        addrs = ", ".join(str(s.getsockname()) for s in self._server.sockets)
        tls_label = "TLS" if self._ssl_context else "plaintext"
        logger.info("DetecGateway listening on %s (%s)", addrs, tls_label)

        async with self._server:
            await self._server.serve_forever()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        peer_ip = peer[0] if peer else "unknown"
        logger.debug("New connection from %s", peer)

        if not await self._track_connect(peer_ip):
            logger.warning(
                "Connection rejected from %s (limit reached: %d global, %d from this IP)",
                peer_ip, self._active_connections,
                self._connections_per_ip.get(peer_ip, 0),
            )
            writer.close()
            return

        session = AgentSession(
            reader,
            writer,
            registry=self._registry,
            label=f"pending:{peer}",
            keepalive_interval=settings.default_heartbeat_interval,
            read_timeout=_READ_TIMEOUT,
        )
        try:
            await session.run()
        except Exception:
            logger.exception("Session error for %s", peer)
        finally:
            if not session.closed:
                await session.close()
            await self._track_disconnect(peer_ip)

    async def stop(self) -> None:
        """Gracefully shut down the gateway."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("DetecGateway stopped")

        for session in await self._registry.all_sessions():
            await session.close()

    async def push_to_endpoint(self, endpoint_id: str, msg: dict[str, Any]) -> bool:
        """Push a message to a specific connected agent. Returns False if not connected."""
        session = await self._registry.get(endpoint_id)
        if not session:
            return False
        try:
            await session.send(msg)
            return True
        except ConnectionError:
            return False

    async def broadcast(self, msg: dict[str, Any]) -> int:
        """Send a message to all connected agents. Returns delivery count."""
        sessions = await self._registry.all_sessions()
        sent = 0
        for session in sessions:
            try:
                await session.send(msg)
                sent += 1
            except ConnectionError:
                continue
        return sent

    async def push_posture(
        self,
        endpoint_id: str,
        posture: str,
        auto_enforce_threshold: float = 0.75,
        allow_list: list[str] | None = None,
    ) -> bool:
        """Push a posture update to a specific connected agent."""
        msg = posture_push_msg(
            posture=posture,
            auto_enforce_threshold=auto_enforce_threshold,
            allow_list=allow_list,
        )
        return await self.push_to_endpoint(endpoint_id, msg)
