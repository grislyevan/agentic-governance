"""Auth router: register, login, refresh, /me."""

from __future__ import annotations

import logging
import re
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

from core.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    is_valid_token,
    verify_password,
)
from core.audit_logger import record as audit_record
from core.database import get_db
from models.tenant import Tenant
from models.user import User, generate_api_key
from schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_current_user(token: str, db: Session) -> User:
    payload = is_valid_token(token)
    if not payload:
        logger.warning("Token validation failed (invalid or expired)")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        logger.warning("Token valid but user %s not found or inactive", payload["sub"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "tenant"


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register(request: Request, body: RegisterRequest, db: Session = Depends(get_db)) -> RegisterResponse:
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        logger.warning("Registration attempt with existing email (domain: %s)", body.email.split("@")[-1] if "@" in body.email else "unknown")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    tenant_name = (body.tenant_name or body.email.split("@")[0]).strip() or "My Org"
    slug = _slugify(tenant_name)
    existing_tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing_tenant:
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"

    tenant = Tenant(id=str(uuid.uuid4()), name=tenant_name, slug=slug)
    db.add(tenant)
    db.flush()

    raw_key, prefix, key_hash = generate_api_key()
    user = User(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        email=body.email,
        hashed_password=hash_password(body.password),
        first_name=body.first_name,
        last_name=body.last_name,
        role="owner",
        api_key_prefix=prefix,
        api_key_hash=key_hash,
    )
    db.add(user)
    db.flush()

    audit_record(
        db,
        tenant_id=tenant.id,
        actor_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        detail={"email": body.email},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    refresh_tok, refresh_jti = create_refresh_token(user.id, tenant.id)
    user.refresh_jti = refresh_jti
    db.commit()

    return RegisterResponse(
        access_token=create_access_token(user.id, tenant.id),
        refresh_token=refresh_tok,
        api_key=raw_key,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        masked = body.email.split("@")[0][:2] + "***@" + body.email.split("@")[-1] if "@" in body.email else "***"
        logger.warning("Failed login attempt for %s", masked)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        logger.warning("Login attempt for disabled account %s", body.email)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    audit_record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    refresh_tok, refresh_jti = create_refresh_token(user.id, user.tenant_id)
    user.refresh_jti = refresh_jti
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=refresh_tok,
    )


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
def refresh_token(request: Request, body: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    payload = is_valid_token(body.refresh_token, token_type="refresh")
    if not payload:
        logger.warning("Invalid refresh token submitted")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        logger.warning("Refresh token valid but user %s not found or inactive", payload["sub"])
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.refresh_jti and payload.get("jti") != user.refresh_jti:
        logger.warning("Refresh token reuse detected for user %s (expected jti=%s, got=%s)",
                        user.id, user.refresh_jti, payload.get("jti"))
        user.refresh_jti = None
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token already used")

    refresh_tok, refresh_jti = create_refresh_token(user.id, user.tenant_id)
    user.refresh_jti = refresh_jti
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=refresh_tok,
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserResponse:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        user = _get_current_user(token, db)
        return UserResponse.model_validate(user)

    if x_api_key:
        from models.user import verify_api_key, API_KEY_PREFIX_LEN
        prefix = x_api_key[:API_KEY_PREFIX_LEN]
        candidates = (
            db.query(User)
            .filter(User.api_key_prefix == prefix, User.is_active.is_(True))
            .all()
        )
        for user in candidates:
            if user.api_key_hash and verify_api_key(x_api_key, user.api_key_hash):
                return UserResponse.model_validate(user)

    logger.warning("GET /auth/me called without valid credentials")
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
