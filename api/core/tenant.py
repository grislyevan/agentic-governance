"""Shared tenant resolution used by all resource routers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.auth import is_valid_token
from models.user import User, verify_api_key, API_KEY_PREFIX_LEN

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AuthContext:
    """Authentication result carrying tenant, user, and role info."""
    tenant_id: str
    user_id: str | None = None
    role: str | None = None


def resolve_auth(authorization: str | None, x_api_key: str | None, db: Session) -> AuthContext:
    """Resolve full auth context from JWT or API key. Raises 401 on failure."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = is_valid_token(token)
        if payload:
            user = db.query(User).filter(User.id == payload["sub"]).first()
            role = user.role if user else None
            return AuthContext(
                tenant_id=payload["tenant_id"],
                user_id=payload["sub"],
                role=role,
            )

    if x_api_key:
        prefix = x_api_key[:API_KEY_PREFIX_LEN]
        candidates = (
            db.query(User)
            .filter(User.api_key_prefix == prefix, User.is_active.is_(True))
            .all()
        )
        for user in candidates:
            if user.api_key_hash and verify_api_key(x_api_key, user.api_key_hash):
                return AuthContext(
                    tenant_id=user.tenant_id,
                    user_id=user.id,
                    role=user.role,
                )

    logger.warning("Authentication failed: no valid JWT or API key provided")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    """Resolve tenant_id from JWT or API key. Raises 401 on failure.

    Convenience wrapper around ``resolve_auth`` for routers that only
    need the tenant_id.
    """
    return resolve_auth(authorization, x_api_key, db).tenant_id


def require_role(
    auth: AuthContext,
    *allowed_roles: str,
) -> None:
    """Raise 403 if the authenticated user's role is not in *allowed_roles*."""
    if auth.role not in allowed_roles:
        logger.warning(
            "Access denied: user %s has role '%s', required one of %s",
            auth.user_id, auth.role, allowed_roles,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
