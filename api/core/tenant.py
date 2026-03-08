"""Shared tenant resolution used by all resource routers."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.auth import is_valid_token
from models.user import User, verify_api_key, API_KEY_PREFIX_LEN

logger = logging.getLogger(__name__)


def get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    """Resolve tenant_id from JWT or API key. Raises 401 on failure."""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = is_valid_token(token)
        if payload:
            return payload["tenant_id"]

    if x_api_key:
        prefix = x_api_key[:API_KEY_PREFIX_LEN]
        candidates = (
            db.query(User)
            .filter(User.api_key_prefix == prefix, User.is_active.is_(True))
            .all()
        )
        for user in candidates:
            if user.api_key_hash and verify_api_key(x_api_key, user.api_key_hash):
                return user.tenant_id

    logger.warning("Authentication failed: no valid JWT or API key provided")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
