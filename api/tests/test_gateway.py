"""Tests for api.gateway: DetecGateway, AgentSession, SessionRegistry."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Ensure api/ and repo root are on sys.path, set test env vars before app imports
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.dirname(_api_dir)
for _p in (_api_dir, _repo_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-unit-tests-only")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "testpass12345")
os.environ.setdefault("TESTING", "1")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.database as _db_mod
from core.database import Base
from models.tenant import Tenant
from models.user import User, generate_api_key
from models.endpoint import Endpoint
from models.event import Event
from core.auth import hash_password
import models  # noqa: F401 — register all ORM models

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_db_mod.engine = _test_engine
_db_mod.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine,
)


def _reset_db():
    """Drop and recreate all tables in the test DB."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)


def _seed_tenant_and_user() -> tuple[str, str]:
    """Create a tenant and user, return (tenant_id, raw_api_key)."""
    db = _db_mod.SessionLocal()
    try:
        tenant_id = str(uuid.uuid4())
        tenant = Tenant(id=tenant_id, name="TestTenant", slug="test-tenant")
        db.add(tenant)
        db.flush()

        raw_key, prefix, key_hash = generate_api_key()
        user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email="gw-test@example.com",
            hashed_password=hash_password("testpass"),
            first_name="GW",
            role="owner",
            api_key_prefix=prefix,
            api_key_hash=key_hash,
        )
        db.add(user)
        db.commit()
        return tenant_id, raw_key
    finally:
        db.close()


class TestSessionRegistry:
    @pytest.mark.asyncio
    async def test_register_and_get(self) -> None:
        from gateway import SessionRegistry, AgentSession

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")
        await registry.register("ep-1", session)

        found = await registry.get("ep-1")
        assert found is session
        assert registry.count == 1

    @pytest.mark.asyncio
    async def test_unregister(self) -> None:
        from gateway import SessionRegistry, AgentSession

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")
        await registry.register("ep-1", session)
        await registry.unregister("ep-1")

        found = await registry.get("ep-1")
        assert found is None

    @pytest.mark.asyncio
    async def test_evicts_stale_session(self) -> None:
        from gateway import SessionRegistry, AgentSession

        registry = SessionRegistry()

        def _make_session():
            r = asyncio.StreamReader()
            t = _MockTransport()
            p = asyncio.StreamReaderProtocol(r)
            t.set_protocol(p)
            p.connection_made(t)
            w = asyncio.StreamWriter(t, p, r, asyncio.get_event_loop())
            return AgentSession(r, w, registry=registry, label="test")

        s1 = _make_session()
        s2 = _make_session()

        await registry.register("ep-1", s1)
        await registry.register("ep-1", s2)

        found = await registry.get("ep-1")
        assert found is s2
        assert s1.closed


class TestAgentSessionAuth:
    @pytest.mark.asyncio
    async def test_auth_success(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import encode_frame, MessageType, HEADER_SIZE, decode_frame

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")

        msg = auth_msg(api_key, "test-host", "0.3.0", seq=1)
        await session.handle_message(msg)

        assert session.authenticated
        assert session.tenant_id == tenant_id
        assert session.endpoint_id is not None

        sent = _extract_messages(transport)
        assert len(sent) >= 1
        assert sent[0]["t"] == MessageType.AUTH_OK
        assert sent[0]["p"]["session_id"] == session.session_id

    @pytest.mark.asyncio
    async def test_auth_bad_key(self) -> None:
        _reset_db()
        _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")

        msg = auth_msg("bad-key-that-does-not-exist", "test-host", "0.3.0")
        await session.handle_message(msg)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_FAIL


class TestAgentSessionEvents:
    @pytest.mark.asyncio
    async def test_ingest_single_event(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg, event_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")

        await session.handle_message(auth_msg(api_key, "evt-host", "0.3.0"))
        transport.data.clear()

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": "tool.detected",
            "event_version": "1.0.0",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "tool": {"name": "cursor", "class": "A"},
        }
        await session.handle_message(event_msg(ev, seq=10))

        sent = _extract_messages(transport)
        ack = next(m for m in sent if m["t"] == MessageType.ACK)
        assert 10 in ack["p"]["seq_ids"]

        db = _db_mod.SessionLocal()
        try:
            stored = db.query(Event).filter(Event.event_id == ev["event_id"]).first()
            assert stored is not None
            assert stored.tool_name == "cursor"
        finally:
            db.close()

    @pytest.mark.asyncio
    async def test_duplicate_event_is_acked(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg, event_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        reader = asyncio.StreamReader()
        transport = _MockTransport()
        protocol = asyncio.StreamReaderProtocol(reader)
        transport.set_protocol(protocol)
        protocol.connection_made(transport)
        writer = asyncio.StreamWriter(transport, protocol, reader, asyncio.get_event_loop())

        session = AgentSession(reader, writer, registry=registry, label="test")
        await session.handle_message(auth_msg(api_key, "dup-host", "0.3.0"))

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": "tool.detected",
            "event_version": "1.0.0",
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }

        transport.data.clear()
        await session.handle_message(event_msg(ev, seq=1))
        transport.data.clear()
        await session.handle_message(event_msg(ev, seq=2))

        sent = _extract_messages(transport)
        ack = next(m for m in sent if m["t"] == MessageType.ACK)
        assert 2 in ack["p"]["seq_ids"]


class TestDetecGateway:
    @pytest.mark.asyncio
    async def test_gateway_starts_and_stops(self) -> None:
        from gateway import DetecGateway

        gw = DetecGateway(host="127.0.0.1", port=0)
        task = asyncio.create_task(gw.serve())
        await asyncio.sleep(0.1)

        assert gw._server is not None
        assert gw._server.is_serving()

        await gw.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# -- Helpers -----------------------------------------------------------------

class _MockTransport(asyncio.Transport):
    def __init__(self):
        super().__init__()
        self.data = bytearray()
        self._closing = False
        self._protocol = None

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    def is_closing(self) -> bool:
        return self._closing

    def close(self) -> None:
        self._closing = True
        if self._protocol and hasattr(self._protocol, "connection_lost"):
            self._protocol.connection_lost(None)

    def get_extra_info(self, name, default=None):
        if name == "peername":
            return ("127.0.0.1", 9999)
        return default

    def set_protocol(self, protocol) -> None:
        self._protocol = protocol

    def get_protocol(self):
        return self._protocol


def _extract_messages(transport: _MockTransport) -> list[dict]:
    """Decode all framed messages from the transport's written bytes."""
    from protocol.wire import FrameReader
    reader = FrameReader()
    reader.feed(bytes(transport.data))
    return reader.messages()
