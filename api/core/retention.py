"""Event retention and purge logic."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from core.config import settings
from models.event import Event
from models.tenant import Tenant

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000


def _effective_retention_days(tenant: Tenant) -> int:
    if tenant.retention_days is not None:
        return tenant.retention_days
    return settings.default_retention_days


def purge_expired_events(db: Session) -> dict[str, int]:
    """Delete events older than each tenant's retention period.

    Runs in batches of BATCH_SIZE per tenant to avoid long-running
    transactions. Returns a dict of tenant_id -> count deleted.
    """
    tenants = db.query(Tenant).all()
    cutoff = datetime.now(timezone.utc)
    totals: dict[str, int] = {}

    for tenant in tenants:
        days = _effective_retention_days(tenant)
        tenant_cutoff = cutoff - timedelta(days=days)
        deleted = 0

        while True:
            subq = (
                db.query(Event.id)
                .filter(
                    Event.tenant_id == tenant.id,
                    Event.observed_at < tenant_cutoff,
                )
                .limit(BATCH_SIZE)
            )
            ids_to_delete = [row[0] for row in subq.all()]
            if not ids_to_delete:
                break

            stmt = delete(Event).where(Event.id.in_(ids_to_delete))
            result = db.execute(stmt)
            batch_count = result.rowcount
            deleted += batch_count
            db.commit()

            if batch_count < BATCH_SIZE:
                break

        if deleted > 0:
            totals[tenant.id] = deleted
            logger.info(
                "Purged %d events for tenant %s (retention %d days)",
                deleted, tenant.id, days,
            )

    return totals


def purge_tenant_events(
    db: Session,
    tenant_id: str,
    older_than_days: int | None = None,
) -> int:
    """Delete events for a single tenant older than the given days.

    If older_than_days is None, uses the tenant's retention_days or
    global default. Returns total count deleted.
    """
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        return 0
    if older_than_days is not None:
        days = older_than_days
    else:
        days = _effective_retention_days(tenant)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    deleted = 0

    while True:
        subq = (
            db.query(Event.id)
            .filter(
                Event.tenant_id == tenant_id,
                Event.observed_at < cutoff,
            )
            .limit(BATCH_SIZE)
        )
        ids_to_delete = [row[0] for row in subq.all()]
        if not ids_to_delete:
            break

        stmt = delete(Event).where(Event.id.in_(ids_to_delete))
        result = db.execute(stmt)
        deleted += result.rowcount
        db.commit()

        if result.rowcount < BATCH_SIZE:
            break

    return deleted
