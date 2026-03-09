"""Shared audit logging helper.

Call ``record()`` from any router to write an immutable entry to the
``audit_log`` table.  The helper resolves the actor from the current
authentication context and captures the caller's IP address.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from models.audit import AuditLog

logger = logging.getLogger(__name__)


def record(
    db: Session,
    *,
    tenant_id: str,
    actor_id: str | None,
    actor_type: str = "user",
    action: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert one audit log entry. Fails silently so it never breaks the
    parent request; errors are logged at WARNING level."""
    try:
        entry = AuditLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            detail=detail or {},
            ip_address=ip_address,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.warning("Failed to write audit log entry", exc_info=True)
