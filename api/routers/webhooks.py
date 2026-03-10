"""Webhook management router: CRUD + test delivery."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.audit import AuditLog
from models.webhook import Webhook, generate_webhook_secret
from schemas.webhooks import WebhookCreate, WebhookListResponse, WebhookOut, WebhookUpdate
from webhooks.sender import deliver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _audit(db: Session, *, tenant_id: str, actor_id: str | None, action: str,
           resource_id: str, detail: dict | None = None) -> None:
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type="user",
        action=action,
        resource_type="webhook",
        resource_id=resource_id,
        detail=detail or {},
    ))


@router.get("", response_model=WebhookListResponse)
def list_webhooks(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> WebhookListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    webhooks = (
        db.query(Webhook)
        .filter(Webhook.tenant_id == auth.tenant_id)
        .order_by(Webhook.created_at)
        .all()
    )

    return WebhookListResponse(
        items=[WebhookOut.model_validate(w) for w in webhooks],
        total=len(webhooks),
    )


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
def create_webhook(
    body: WebhookCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> WebhookOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    webhook = Webhook(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        url=body.url,
        secret=generate_webhook_secret(),
        events=json.dumps(body.events),
        is_active=body.is_active,
    )
    db.add(webhook)
    _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
           action="webhook.created", resource_id=webhook.id,
           detail={"url": body.url, "events": body.events})
    db.commit()
    db.refresh(webhook)

    logger.info("Webhook %s created by %s", webhook.id, auth.user_id)
    return WebhookOut.model_validate(webhook)


@router.patch("/{webhook_id}", response_model=WebhookOut)
def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> WebhookOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.tenant_id == auth.tenant_id)
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    changes: dict = {}
    update_data = body.model_dump(exclude_unset=True)

    if "url" in update_data:
        webhook.url = update_data["url"]
        changes["url"] = update_data["url"]
    if "events" in update_data:
        webhook.events = json.dumps(update_data["events"])
        changes["events"] = update_data["events"]
    if "is_active" in update_data:
        webhook.is_active = update_data["is_active"]
        changes["is_active"] = update_data["is_active"]

    if changes:
        _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
               action="webhook.updated", resource_id=webhook.id, detail=changes)
        db.commit()
        db.refresh(webhook)

    return WebhookOut.model_validate(webhook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.tenant_id == auth.tenant_id)
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
           action="webhook.deleted", resource_id=webhook.id,
           detail={"url": webhook.url})
    db.delete(webhook)
    db.commit()

    logger.info("Webhook %s deleted by %s", webhook_id, auth.user_id)


@router.post("/{webhook_id}/test", response_model=dict)
async def test_webhook(
    webhook_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    webhook = (
        db.query(Webhook)
        .filter(Webhook.id == webhook_id, Webhook.tenant_id == auth.tenant_id)
        .first()
    )
    if not webhook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    test_payload = {
        "event_id": f"test-{uuid.uuid4().hex[:8]}",
        "event_type": "webhook.test",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "tenant_id": auth.tenant_id,
        "tool": {"name": "test", "class": "test", "version": "0.0.0"},
        "policy": {"decision_state": "test", "rule_id": None},
        "severity": {"level": "info"},
        "endpoint": {"hostname": "test"},
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "test": True,
    }

    success = await deliver(webhook.url, webhook.secret, test_payload)

    _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
           action="webhook.tested", resource_id=webhook.id,
           detail={"url": webhook.url, "success": success})
    db.commit()

    return {"success": success, "webhook_id": webhook_id}
