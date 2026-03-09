"""User management router: CRUD for tenant users (owner/admin only)."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.auth import hash_password
from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.audit import AuditLog
from models.user import User
from schemas.users import UserCreate, UserListResponse, UserOut, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


def _audit(db: Session, *, tenant_id: str, actor_id: str | None, action: str,
           resource_id: str, detail: dict | None = None) -> None:
    db.add(AuditLog(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type="user",
        action=action,
        resource_type="user",
        resource_id=resource_id,
        detail=detail or {},
    ))


@router.get("", response_model=UserListResponse)
def list_users(
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> UserListResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    q = db.query(User).filter(User.tenant_id == auth.tenant_id)

    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (User.email.ilike(pattern))
            | (User.first_name.ilike(pattern))
            | (User.last_name.ilike(pattern))
        )

    total = q.with_entities(func.count()).scalar() or 0
    items = (
        q.order_by(User.created_at)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return UserListResponse(
        items=[UserOut.model_validate(u) for u in items],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> UserOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        logger.warning("User creation failed: email %s already exists", body.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        )

    user = User(
        id=str(uuid.uuid4()),
        tenant_id=auth.tenant_id,
        email=body.email,
        hashed_password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        auth_provider="local",
        password_reset_required=True,
    )
    db.add(user)
    _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
           action="user.created", resource_id=user.id,
           detail={"email": body.email, "role": body.role})
    db.commit()
    db.refresh(user)

    logger.info("User %s created by %s in tenant %s", user.email, auth.user_id, auth.tenant_id)
    return UserOut.model_validate(user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> UserOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    user = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == auth.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    body: UserUpdate,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> UserOut:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    user = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == auth.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The tenant owner cannot be modified",
        )

    changes: dict = {}
    update_data = body.model_dump(exclude_unset=True)

    if "first_name" in update_data:
        user.first_name = update_data["first_name"]
        changes["first_name"] = update_data["first_name"]

    if "last_name" in update_data:
        user.last_name = update_data["last_name"]
        changes["last_name"] = update_data["last_name"]

    if "role" in update_data:
        user.role = update_data["role"]
        changes["role"] = update_data["role"]

    if "is_active" in update_data:
        if user.id == auth.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot deactivate yourself",
            )
        user.is_active = update_data["is_active"]
        changes["is_active"] = update_data["is_active"]

    if changes:
        _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
               action="user.updated", resource_id=user.id, detail=changes)
        db.commit()
        db.refresh(user)
        logger.info("User %s updated by %s: %s", user.email, auth.user_id, changes)

    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> None:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner")

    user = (
        db.query(User)
        .filter(User.id == user_id, User.tenant_id == auth.tenant_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The tenant owner cannot be deactivated",
        )

    if user.id == auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate yourself",
        )

    user.is_active = False
    _audit(db, tenant_id=auth.tenant_id, actor_id=auth.user_id,
           action="user.deactivated", resource_id=user.id,
           detail={"email": user.email})
    db.commit()
    logger.info("User %s deactivated by %s", user.email, auth.user_id)
