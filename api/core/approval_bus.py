"""
In-process approval event bus.

Publishes approval lifecycle events to all SSE subscribers for a given tenant.
Each subscriber holds an asyncio.Queue. On publish, the payload is put into
every queue registered for that tenant_id.

Thread safety: all mutations are protected by an asyncio.Lock acquired in
async context. Sync callers (router handlers) must use publish_sync() which
schedules the coroutine on the running event loop.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger("agentic_governance")

# tenant_id → list of queues (one per SSE connection)
_channels: dict[str, list[asyncio.Queue]] = defaultdict(list)
_lock = asyncio.Lock()


async def subscribe(tenant_id: str) -> asyncio.Queue:
    """Register a new subscriber for tenant_id. Returns the queue to read from."""
    q: asyncio.Queue = asyncio.Queue(maxsize=64)
    async with _lock:
        _channels[tenant_id].append(q)
    logger.debug(
        "SSE subscribe: tenant=%s total=%d", tenant_id, len(_channels[tenant_id])
    )
    return q


async def unsubscribe(tenant_id: str, q: asyncio.Queue) -> None:
    """Remove a subscriber queue. Safe to call on disconnect."""
    async with _lock:
        try:
            _channels[tenant_id].remove(q)
        except ValueError:
            pass
        if not _channels[tenant_id]:
            del _channels[tenant_id]
    logger.debug("SSE unsubscribe: tenant=%s", tenant_id)


async def publish(tenant_id: str, payload: dict) -> None:
    """Push payload to all subscribers for tenant_id. Non-blocking (put_nowait)."""
    async with _lock:
        queues = list(_channels.get(tenant_id, []))
    dropped = 0
    for q in queues:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dropped += 1
    if dropped:
        logger.warning(
            "SSE bus: dropped %d message(s) for tenant=%s (queues full)",
            dropped,
            tenant_id,
        )


def publish_sync(tenant_id: str, payload: dict) -> None:
    """Synchronous publish for use from non-async router handlers.

    Schedules publish() on the running event loop. Safe to call from
    sync FastAPI route handlers. No-ops if no event loop is running.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(publish(tenant_id, payload))
    except RuntimeError:
        pass
