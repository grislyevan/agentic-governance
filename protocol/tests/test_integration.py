"""End-to-end integration test: gateway + TcpEmitter over loopback.

Starts a DetecGateway on a random port, connects a TcpEmitter, sends
events and heartbeats, and verifies they arrive at the server. Uses an
in-memory SQLite database.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# Ensure api/ and repo root are importable
_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_api_dir = os.path.join(_repo_root, "api")
for _p in (_repo_root, _api_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-integration")
os.environ.setdefault("SEED_ADMIN_PASSWORD", "testpass12345")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("GATEWAY_ENABLED", "false")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import core.database as _db_mod
from core.database import Base
from core.auth import hash_password
from models.tenant import Tenant
from models.user import User, generate_api_key
from models.endpoint import Endpoint
from models.event import Event
import models  # noqa: F401

_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_db_mod.engine = _test_engine
_db_mod.SessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=_test_engine,
)


def _setup_db_and_seed() -> tuple[str, str]:
    """Create tables and seed a tenant + user. Returns (tenant_id, api_key)."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    db = _db_mod.SessionLocal()
    try:
        tenant_id = str(uuid.uuid4())
        tenant = Tenant(id=tenant_id, name="IntegTest", slug="integ-test")
        db.add(tenant)
        db.flush()

        raw_key, prefix, key_hash = generate_api_key()
        user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email="integ@test.com",
            hashed_password=hash_password("testpass"),
            first_name="Integ",
            role="owner",
            api_key_prefix=prefix,
            api_key_hash=key_hash,
        )
        db.add(user)
        db.commit()
        return tenant_id, raw_key
    finally:
        db.close()


@pytest.mark.asyncio
async def test_gateway_and_tcp_emitter_end_to_end() -> None:
    """Start gateway, connect TcpEmitter, send events, verify ingestion."""
    tenant_id, api_key = _setup_db_and_seed()

    from gateway import DetecGateway

    gw = DetecGateway(host="127.0.0.1", port=0)
    gw_task = asyncio.create_task(gw.serve())

    await asyncio.sleep(0.2)
    assert gw._server is not None

    port = gw._server.sockets[0].getsockname()[1]

    from collector.output.tcp_emitter import TcpEmitter

    emitter = TcpEmitter(
        gateway_host="127.0.0.1",
        gateway_port=port,
        api_key=api_key,
        hostname="integ-test-host",
        agent_version="0.3.0",
    )

    event_ids = []
    for i in range(3):
        eid = str(uuid.uuid4())
        event_ids.append(eid)
        emitter.emit({
            "event_id": eid,
            "event_type": "tool.detected",
            "event_version": "1.0.0",
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "tool": {"name": f"test-tool-{i}", "class": "A"},
        })

    emitter.heartbeat("integ-test-host", interval_seconds=300)

    # Give time for the background thread to connect, auth, and send
    await asyncio.sleep(3.0)

    db = _db_mod.SessionLocal()
    try:
        events = db.query(Event).filter(Event.tenant_id == tenant_id).all()
        stored_ids = {e.event_id for e in events}

        for eid in event_ids:
            assert eid in stored_ids, f"Event {eid} not found in DB"

        ep = db.query(Endpoint).filter(
            Endpoint.tenant_id == tenant_id,
            Endpoint.hostname == "integ-test-host",
        ).first()
        assert ep is not None
        assert ep.last_seen_at is not None
    finally:
        db.close()

    emitter.shutdown()
    await gw.stop()
    gw_task.cancel()
    try:
        await gw_task
    except asyncio.CancelledError:
        pass
