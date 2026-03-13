"""Response playbooks router: CRUD and dry-run."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.audit_logger import record as audit_record
from core.database import get_db
from core.response_playbooks import get_default_playbooks, match_trigger
from core.tenant import resolve_auth, require_role
from models.response_playbook import ResponsePlaybook
from schemas.response_playbooks import (
    PlaybookTestRequest,
    PlaybookTestResponse,
    ResponsePlaybookCreate,
    ResponsePlaybookListResponse,
    ResponsePlaybookOut,
    ResponsePlaybookUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


def _playbook_to_out(pb: ResponsePlaybook) -> ResponsePlaybookOut:
    trigger = {}
    try:
        trigger = json.loads(pb.trigger) if pb.trigger else {}
    except (json.JSONDecodeError, TypeError):
        pass
    actions = []
    try:
        actions = json.loads(pb.actions) if pb.actions else []
    except (json.JSONDecodeError, TypeError):
        pass
    escalation = None
    if pb.escalation:
        try:
            escalation = json.loads(pb.escalation)
        except (json.JSONDecodeError, TypeError):
            pass
    return ResponsePlaybookOut(
        id=pb.id,
        tenant_id=pb.tenant_id,
        name=pb.name,
        description=pb.description,
        trigger=trigger,
        actions=actions,
        escalation=escalation,
        is_active=pb.is_active,
        created_at=pb.created_at,
        updated_at=pb.updated_at,
    )


@router.get("", response_model=ResponsePlaybookListResponse)
def list_playbooks(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ResponsePlaybookListResponse:
    """List default playbooks plus tenant custom playbooks."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst", "viewer")

    defaults = get_default_playbooks()
    custom = (
        db.query(ResponsePlaybook)
        .filter(ResponsePlaybook.tenant_id == auth.tenant_id)
        .order_by(ResponsePlaybook.name)
        .all()
    )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    items: list[ResponsePlaybookOut] = []
    for pid, defn in defaults.items():
        items.append(
            ResponsePlaybookOut(
                id=pid,
                tenant_id=auth.tenant_id,
                name=defn.get("name", pid),
                description=defn.get("description"),
                trigger=defn.get("trigger") or {},
                actions=defn.get("actions") or [],
                escalation=defn.get("escalation"),
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
    for pb in custom:
        items.append(_playbook_to_out(pb))

    return ResponsePlaybookListResponse(items=items, total=len(items))


@router.get("/{playbook_id}", response_model=ResponsePlaybookOut)
def get_playbook(
    playbook_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ResponsePlaybookOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin", "analyst", "viewer")

    defaults = get_default_playbooks()
    if playbook_id in defaults:
        defn = defaults[playbook_id]
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return ResponsePlaybookOut(
            id=playbook_id,
            tenant_id=auth.tenant_id,
            name=defn.get("name", playbook_id),
            description=defn.get("description"),
            trigger=defn.get("trigger") or {},
            actions=defn.get("actions") or [],
            escalation=defn.get("escalation"),
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    pb = (
        db.query(ResponsePlaybook)
        .filter(
            ResponsePlaybook.id == playbook_id,
            ResponsePlaybook.tenant_id == auth.tenant_id,
        )
        .first()
    )
    if not pb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    return _playbook_to_out(pb)


@router.post("", response_model=ResponsePlaybookOut, status_code=status.HTTP_201_CREATED)
def create_playbook(
    body: ResponsePlaybookCreate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ResponsePlaybookOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    pb = ResponsePlaybook(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        name=body.name,
        description=body.description,
        trigger=json.dumps(body.trigger),
        actions=json.dumps(body.actions),
        escalation=json.dumps(body.escalation) if body.escalation else None,
        is_active=body.is_active,
    )
    db.add(pb)
    db.flush()
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        actor_type="user",
        action="playbook.created",
        resource_type="playbook",
        resource_id=pb.id,
        detail={"name": pb.name},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(pb)
    return _playbook_to_out(pb)


@router.put("/{playbook_id}", response_model=ResponsePlaybookOut)
def update_playbook(
    playbook_id: str,
    body: ResponsePlaybookUpdate,
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> ResponsePlaybookOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    if playbook_id in get_default_playbooks():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update default playbook",
        )

    pb = (
        db.query(ResponsePlaybook)
        .filter(
            ResponsePlaybook.id == playbook_id,
            ResponsePlaybook.tenant_id == auth.tenant_id,
        )
        .first()
    )
    if not pb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")

    data = body.model_dump(exclude_unset=True)
    if "trigger" in data:
        pb.trigger = json.dumps(data["trigger"])
    if "actions" in data:
        pb.actions = json.dumps(data["actions"])
    if "escalation" in data:
        pb.escalation = json.dumps(data["escalation"]) if data["escalation"] is not None else None
    for key in ("name", "description", "is_active"):
        if key in data:
            setattr(pb, key, data[key])
    db.flush()
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        actor_type="user",
        action="playbook.updated",
        resource_type="playbook",
        resource_id=pb.id,
        detail={"name": pb.name, "changes": list(data.keys())},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(pb)
    return _playbook_to_out(pb)


@router.post("/restore-defaults", status_code=status.HTTP_200_OK)
def restore_default_playbooks(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> dict:
    """Remove all custom playbooks for the tenant. Default playbooks remain available.
    Requires owner or admin. Logged in audit."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    deleted = (
        db.query(ResponsePlaybook)
        .filter(ResponsePlaybook.tenant_id == auth.tenant_id)
        .delete()
    )
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        actor_type="user",
        action="playbooks.restore_defaults",
        resource_type="playbook",
        resource_id="",
        detail={"deleted_count": deleted},
    )
    db.commit()
    return {"restored": True, "deleted_custom_playbooks": deleted}


@router.delete("/{playbook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_playbook(
    playbook_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    if playbook_id in get_default_playbooks():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default playbook",
        )

    pb = (
        db.query(ResponsePlaybook)
        .filter(
            ResponsePlaybook.id == playbook_id,
            ResponsePlaybook.tenant_id == auth.tenant_id,
        )
        .first()
    )
    if not pb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
    db.delete(pb)
    db.commit()


@router.post("/{playbook_id}/test", response_model=PlaybookTestResponse)
def test_playbook(
    playbook_id: str,
    body: PlaybookTestRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> PlaybookTestResponse:
    """Dry-run: match a sample event against the playbook and return matched + actions_run."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    defaults = get_default_playbooks()
    if playbook_id in defaults:
        defn = defaults[playbook_id]
        trigger = defn.get("trigger") or {}
        actions = defn.get("actions") or []
    else:
        pb = (
            db.query(ResponsePlaybook)
            .filter(
                ResponsePlaybook.id == playbook_id,
                ResponsePlaybook.tenant_id == auth.tenant_id,
            )
            .first()
        )
        if not pb:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Playbook not found")
        try:
            trigger = json.loads(pb.trigger) if pb.trigger else {}
        except (json.JSONDecodeError, TypeError):
            trigger = {}
        try:
            actions = json.loads(pb.actions) if pb.actions else []
        except (json.JSONDecodeError, TypeError):
            actions = []

    matched = match_trigger(trigger, body.event_payload)
    actions_run: list[dict] = []
    if matched:
        for a in actions:
            actions_run.append({"type": a.get("type"), "status": "dry_run"})

    return PlaybookTestResponse(
        playbook_id=playbook_id,
        matched=matched,
        actions_run=actions_run,
    )
