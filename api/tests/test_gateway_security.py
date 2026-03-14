"""Gateway protocol security tests: auth bypass, fuzzing, tenant key auth."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_repo_root = os.path.dirname(_api_dir)
for _p in (_api_dir, _repo_root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

import core.database as _db_mod
from core.database import Base
from models.tenant import Tenant
from models.user import User, generate_api_key
from core.auth import hash_password
import models  # noqa: F401

_test_engine = _db_mod.engine


def _reset_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)


def _seed_tenant_and_user() -> tuple[str, str]:
    """Create a tenant and user with API key; return (tenant_id, raw_api_key)."""
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
            email="gw-sec@example.com",
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


def _seed_tenant_with_agent_key() -> tuple[str, str]:
    """Create a tenant with agent_key only (no user API key); return (tenant_id, agent_key)."""
    db = _db_mod.SessionLocal()
    try:
        tenant_id = str(uuid.uuid4())
        from models.tenant import generate_agent_key
        agent_key = generate_agent_key()
        tenant = Tenant(
            id=tenant_id,
            name="AgentKeyTenant",
            slug="agent-key-tenant",
            agent_key=agent_key,
        )
        db.add(tenant)
        db.commit()
        return tenant_id, agent_key
    finally:
        db.close()


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
    from protocol.wire import FrameReader
    reader = FrameReader()
    reader.feed(bytes(transport.data))
    return reader.messages()


def _make_session(registry):
    from gateway import AgentSession
    reader = asyncio.StreamReader()
    transport = _MockTransport()
    protocol = asyncio.StreamReaderProtocol(reader)
    transport.set_protocol(protocol)
    protocol.connection_made(transport)
    writer = asyncio.StreamWriter(
        transport, protocol, reader, asyncio.get_event_loop()
    )
    return AgentSession(reader, writer, registry=registry, label="test"), transport


# ---------------------------------------------------------------------------
# Auth bypass: send event before AUTH
# ---------------------------------------------------------------------------


class TestGatewayAuthBypass:
    @pytest.mark.asyncio
    async def test_event_before_auth_rejected(self) -> None:
        _reset_db()
        _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg, event_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        ev = {
            "event_id": str(uuid.uuid4()),
            "event_type": "tool.detected",
            "event_version": "1.0",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "tool": {"name": "cursor"},
        }
        await session.handle_message(event_msg(ev, seq=1))

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert len(sent) >= 1
        assert sent[0]["t"] == MessageType.AUTH_FAIL
        assert "Must authenticate first" in sent[0]["p"].get("reason", "")

    @pytest.mark.asyncio
    async def test_heartbeat_before_auth_rejected(self) -> None:
        _reset_db()
        _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        hb = {"t": MessageType.HEARTBEAT, "id": 0, "ts": 0, "p": {}}
        await session.handle_message(hb)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert len(sent) >= 1
        assert sent[0]["t"] == MessageType.AUTH_FAIL


# ---------------------------------------------------------------------------
# Malformed auth payload
# ---------------------------------------------------------------------------


class TestGatewayMalformedAuth:
    @pytest.mark.asyncio
    async def test_auth_with_empty_api_key_rejected(self) -> None:
        _reset_db()
        _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        msg = auth_msg("", "host", "0.3.0")
        await session.handle_message(msg)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_FAIL
        assert "Missing" in sent[0]["p"].get("reason", "") or "Invalid" in sent[0]["p"].get("reason", "")

    @pytest.mark.asyncio
    async def test_auth_with_empty_hostname_rejected(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        msg = auth_msg(api_key, "", "0.3.0")
        await session.handle_message(msg)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_FAIL

    @pytest.mark.asyncio
    async def test_auth_with_hostname_too_long_rejected(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        long_hostname = "x" * 256
        msg = auth_msg(api_key, long_hostname, "0.3.0")
        await session.handle_message(msg)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_FAIL
        assert "too long" in sent[0]["p"].get("reason", "").lower()


# ---------------------------------------------------------------------------
# Tenant agent key auth (gateway accepts tenant agent keys)
# ---------------------------------------------------------------------------


class TestGatewayTenantAgentKeyAuth:
    @pytest.mark.asyncio
    async def test_tenant_agent_key_auth_success(self) -> None:
        _reset_db()
        tenant_id, agent_key = _seed_tenant_with_agent_key()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        msg = auth_msg(agent_key, "agent-key-host", "0.3.0", seq=1)
        await session.handle_message(msg)

        assert session.authenticated
        assert session.tenant_id == tenant_id
        assert session.endpoint_id is not None
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_OK


# ---------------------------------------------------------------------------
# Malformed msgpack / frame injection
# ---------------------------------------------------------------------------


class TestGatewayFrameFuzzing:
    @pytest.mark.asyncio
    async def test_message_with_wrong_type_field_handled(self) -> None:
        _reset_db()
        tenant_id, api_key = _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.messages import auth_msg
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)
        await session.handle_message(auth_msg(api_key, "fuzz-host", "0.3.0"))
        transport.data.clear()

        unknown_type_msg = {"t": 0x99, "id": 1, "ts": 0, "p": {}}
        await session.handle_message(unknown_type_msg)

        sent = _extract_messages(transport)
        assert any(m["t"] == MessageType.ERROR for m in sent)

    @pytest.mark.asyncio
    async def test_auth_payload_not_dict_rejected(self) -> None:
        _reset_db()
        _seed_tenant_and_user()

        from gateway import AgentSession, SessionRegistry
        from protocol.wire import MessageType

        registry = SessionRegistry()
        session, transport = _make_session(registry)

        msg = {"t": MessageType.AUTH, "id": 0, "ts": 0, "p": "not-a-dict"}
        await session.handle_message(msg)

        assert not session.authenticated
        sent = _extract_messages(transport)
        assert sent[0]["t"] == MessageType.AUTH_FAIL
        assert "Invalid" in sent[0]["p"].get("reason", "")
