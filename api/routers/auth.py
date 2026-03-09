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
        full_name=body.full_name,
        role="admin",
        api_key_prefix=prefix,
        api_key_hash=key_hash,
    )
    db.add(user)
    db.commit()

    return RegisterResponse(
        access_token=create_access_token(user.id, tenant.id),
        refresh_token=create_refresh_token(user.id, tenant.id),
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

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
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

    return TokenResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=create_refresh_token(user.id, user.tenant_id),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserResponse:
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("GET /auth/me called without Authorization header")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    user = _get_current_user(token, db)
    return UserResponse.model_validate(user)
