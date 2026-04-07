"""Shared tenant resolution used by all resource routers."""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from core.auth import is_valid_token
from models.user import VALID_ROLES, User, verify_api_key, API_KEY_PREFIX_LEN

AGENT_KEY_PREFIX_LEN = 8


def _hash_agent_key(raw_key: str) -> str:
    """SHA-256 hash of the raw agent key for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_agent_key() -> tuple[str, str, str]:
    """Generate a new tenant agent key. Returns (full_key, prefix, hash)."""
    raw = secrets.token_hex(32)
    return raw, raw[:AGENT_KEY_PREFIX_LEN], _hash_agent_key(raw)


def verify_agent_key(raw_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of a raw agent key against the stored hash."""
    return hmac.compare_digest(_hash_agent_key(raw_key), stored_hash)


logger = logging.getLogger(__name__)

CROSS_TENANT_ROLES = ("owner", "admin")
AGENT_ROLE = "agent"


@dataclass(frozen=True)
class AuthContext:
    """Authentication result carrying tenant, user, and role info."""

    tenant_id: str
    user_id: str | None = None
    role: str | None = None


def resolve_auth(
    authorization: str | None, x_api_key: str | None, db: Session
) -> AuthContext:
    """Resolve full auth context from JWT, user API key, or tenant agent key.

    Lookup order:
      1. JWT Bearer token
      2. User API key (prefix match + hash verify)
      3. Tenant agent key (prefix match + hash verify)
    Raises 401 on failure.  Tenants without a hashed agent key are
    rejected -- run key rotation to fix.
    """
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

        from models.tenant import Tenant

        _INACTIVE_SUBSCRIPTION_STATUSES = {"canceled", "past_due", "unpaid"}

        # Per-endpoint key lookup (takes priority over tenant key).
        # Agents configured with a per-endpoint key will match here; the
        # tenant context is derived from the endpoint's tenant_id.
        ep_prefix = x_api_key[:AGENT_KEY_PREFIX_LEN]
        from models.endpoint import Endpoint

        ep_candidates = (
            db.query(Endpoint).filter(Endpoint.agent_key_prefix == ep_prefix).all()
        )
        for ep in ep_candidates:
            if ep.agent_key_hash and verify_agent_key(x_api_key, ep.agent_key_hash):
                # Validate the parent tenant is still active
                tenant = db.query(Tenant).filter(Tenant.id == ep.tenant_id).first()
                if (
                    tenant
                    and getattr(tenant, "subscription_status", None)
                    in _INACTIVE_SUBSCRIPTION_STATUSES
                ):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Subscription inactive",
                    )
                return AuthContext(
                    tenant_id=ep.tenant_id,
                    user_id=None,
                    role=AGENT_ROLE,
                )

        # Tenant-level agent key lookup (fleet-wide key)
        prefix = x_api_key[:AGENT_KEY_PREFIX_LEN]
        candidates = db.query(Tenant).filter(Tenant.agent_key_prefix == prefix).all()
        for candidate in candidates:
            if candidate.agent_key_hash and verify_agent_key(
                x_api_key, candidate.agent_key_hash
            ):
                # Don't authenticate tenants with inactive subscriptions
                if (
                    getattr(candidate, "subscription_status", None)
                    in _INACTIVE_SUBSCRIPTION_STATUSES
                ):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Subscription inactive",
                    )
                return AuthContext(
                    tenant_id=candidate.id,
                    user_id=None,
                    role=AGENT_ROLE,
                )
    logger.warning("Authentication failed: no valid JWT or API key provided")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
    )


def get_tenant_id(authorization: str | None, x_api_key: str | None, db: Session) -> str:
    """Resolve tenant_id from JWT or API key. Raises 401 on failure.

    Convenience wrapper around ``resolve_auth`` for routers that only
    need the tenant_id.
    """
    return resolve_auth(authorization, x_api_key, db).tenant_id


def get_tenant_filter(auth: AuthContext, model):
    """Return a SQLAlchemy filter expression for tenant scoping.

    Owner and admin roles see data across all tenants (read-only
    cross-tenant visibility for LIST operations only).  Analyst and
    viewer remain scoped to their own tenant.

    IMPORTANT: Use strict_tenant_filter() for all mutation paths
    (PATCH, DELETE, get-by-id used for writes).  This function must
    only be used for read-list operations.  Using it on write paths
    allows owner/admin to mutate resources belonging to any tenant
    (BOLA/IDOR vulnerability).
    """
    if auth.role in CROSS_TENANT_ROLES:
        # Use a column reference (always true for non-nullable tenant_id)
        # instead of sa.true() so that with_entities(func.count()) keeps
        # the FROM clause when no other column is selected.
        return model.tenant_id.isnot(None)
    return model.tenant_id == auth.tenant_id


def strict_tenant_filter(auth: AuthContext, model):
    """Return a strict tenant filter scoped to auth.tenant_id regardless of role.

    Must be used for all mutation paths (PATCH, PUT, DELETE) and for
    get-by-id lookups that precede a write.  Unlike get_tenant_filter(),
    this always scopes to the authenticated tenant — even for owner/admin
    — preventing cross-tenant mutation via known resource IDs (BOLA fix).
    """
    return model.tenant_id == auth.tenant_id


def require_role(
    auth: AuthContext,
    *allowed_roles: str,
) -> None:
    """Raise 403 if the authenticated user's role is not in *allowed_roles*."""
    if auth.role not in allowed_roles:
        logger.warning(
            "Access denied: user %s has role '%s', required one of %s",
            auth.user_id,
            auth.role,
            allowed_roles,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
