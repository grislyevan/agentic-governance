"""Background loops: staleness monitor and retention purge."""

from __future__ import annotations

import asyncio
import logging

from core.database import SessionLocal
from models.endpoint import Endpoint

logger = logging.getLogger("agentic_governance")

STALENESS_CHECK_INTERVAL = 60
PURGE_INTERVAL_SECONDS = 6 * 60 * 60


async def retention_purge_loop() -> None:
    await asyncio.sleep(60)
    while True:
        db = SessionLocal()
        try:
            from core.retention import purge_expired_events
            purge_expired_events(db)
        except Exception:
            logger.warning("Retention purge cycle failed", exc_info=True)
        finally:
            db.close()
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)


async def staleness_monitor() -> None:
    """Update endpoint status from heartbeat timing."""
    while True:
        await asyncio.sleep(STALENESS_CHECK_INTERVAL)
        db = SessionLocal()
        try:
            all_endpoints = db.query(Endpoint).all()
            for ep in all_endpoints:
                new_status = ep.compute_status()
                if new_status != ep.status:
                    old = ep.status
                    ep.status = new_status
                    logger.info(
                        "Endpoint %s (%s) status %s -> %s",
                        ep.hostname, ep.id, old, new_status,
                    )
            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Staleness monitor cycle failed", exc_info=True)
        finally:
            db.close()
