"""Auth router: register, login, refresh, /me, forgot/reset password, accept invite, SSO."""

from __future__ import annotations

import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.rate_limit import limiter

logger = logging.getLogger(__name__)

from core.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    is_valid_token,
    verify_password,
)
from core.audit_logger import record as audit_record
from core.database import get_db
from models.auth_token import AuthToken, hash_token
from models.tenant import Tenant
from models.user import User, generate_api_key
from schemas.auth import (
    AcceptInviteRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    PasswordResetResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
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
@limiter.limit("3/minute")
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


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)) -> LoginResponse:
    user = db.query(User).filter(User.email == body.email).first()
    if user and user.auth_provider != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account uses SSO. Please sign in with your identity provider.",
        )
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

    return LoginResponse(
        access_token=create_access_token(user.id, user.tenant_id),
        refresh_token=refresh_tok,
        password_reset_required=user.password_reset_required,
    )


@router.post("/forgot-password", response_model=PasswordResetResponse)
@limiter.limit("3/minute")
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    """Request a password reset. Creates a reset token (valid 1 hour).

    Always returns 200 to avoid leaking whether an email exists.
    When SMTP is configured the token is emailed; otherwise it is logged
    server-side at DEBUG level for development use only.
    """
    from core.config import settings as _settings

    user = db.query(User).filter(User.email == body.email, User.is_active.is_(True)).first()
    if not user:
        return PasswordResetResponse(message="If that email is registered, a reset link has been created.")
    if user.auth_provider != "local":
        return PasswordResetResponse(message="If that email is registered, a reset link has been created.")

    db.query(AuthToken).filter(
        AuthToken.user_id == user.id,
        AuthToken.purpose == "reset",
        AuthToken.used_at.is_(None),
    ).update({"used_at": datetime.now(timezone.utc)})

    token_obj, raw_token = AuthToken.create_reset_token(user.id)
    db.add(token_obj)

    audit_record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="password.reset_requested",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    if _settings.smtp_configured:
        logger.info("Password reset token created for %s (email delivery pending)", body.email)
    else:
        logger.debug("Password reset token for %s (no SMTP): %s", body.email, raw_token)

    return PasswordResetResponse(
        message="If that email is registered, a reset link has been created.",
    )


@router.post("/reset-password", response_model=PasswordResetResponse)
@limiter.limit("5/minute")
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    """Reset password using a valid reset token."""
    token_hash = hash_token(body.token)
    token_obj = db.query(AuthToken).filter(
        AuthToken.token_hash == token_hash,
        AuthToken.purpose == "reset",
    ).first()

    if not token_obj or not token_obj.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user = db.query(User).filter(User.id == token_obj.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_required = False
    token_obj.used_at = datetime.now(timezone.utc)

    audit_record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="password.reset_completed",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return PasswordResetResponse(message="Password has been reset successfully.")


@router.post("/accept-invite", response_model=PasswordResetResponse)
@limiter.limit("10/minute")
def accept_invite(
    request: Request,
    body: AcceptInviteRequest,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    """Accept an invite and set a password for the new user account."""
    token_hash = hash_token(body.token)
    token_obj = db.query(AuthToken).filter(
        AuthToken.token_hash == token_hash,
        AuthToken.purpose == "invite",
    ).first()

    if not token_obj or not token_obj.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        )

    user = db.query(User).filter(User.id == token_obj.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        )

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_required = False
    token_obj.used_at = datetime.now(timezone.utc)

    audit_record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="invite.accepted",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return PasswordResetResponse(message="Account activated. You can now sign in.")


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


# ---------------------------------------------------------------------------
# SSO / OIDC
# ---------------------------------------------------------------------------


class SsoCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048)
    state: str = Field(..., min_length=1, max_length=512)


@router.get("/sso/status")
def sso_status() -> dict:
    """Return whether SSO is configured. Used by the dashboard to show/hide the SSO button."""
    from core.config import settings
    out: dict = {"configured": settings.oidc_configured}
    if settings.oidc_configured and settings.oidc_issuer:
        out["issuer"] = settings.oidc_issuer
    return out


@router.get("/sso/login")
def sso_login(request: Request) -> RedirectResponse:
    """Redirect to IdP authorization endpoint. Returns 503 if OIDC not configured."""
    from core.config import settings

    if not settings.oidc_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO is not configured",
        )
    if not settings.oidc_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC redirect URI is not configured",
        )

    import httpx
    from authlib.integrations.httpx_client import AsyncOAuth2Client
    from authlib.common.security import generate_token

    discovery_url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    with httpx.Client() as client:
        resp = client.get(discovery_url)
        resp.raise_for_status()
        metadata = resp.json()

    auth_endpoint = metadata.get("authorization_endpoint")
    if not auth_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery failed: no authorization_endpoint",
        )

    import jwt as pyjwt

    nonce = generate_token(48)
    state_jwt = pyjwt.encode(
        {
            "nonce": nonce,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )

    client = AsyncOAuth2Client(
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        scope="openid profile email",
        redirect_uri=settings.oidc_redirect_uri,
    )
    uri, _ = client.create_authorization_url(
        auth_endpoint,
        state=state_jwt,
        nonce=nonce,
    )
    return RedirectResponse(url=uri, status_code=status.HTTP_302_FOUND)


@router.post("/sso/callback", response_model=TokenResponse)
@limiter.limit("10/minute")
def sso_callback(
    request: Request,
    body: SsoCallbackRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Exchange authorization code for tokens, validate ID token, create or log in user."""
    from core.config import settings
    import httpx
    from authlib.integrations.httpx_client import OAuth2Client

    if not settings.oidc_configured or not settings.oidc_redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO is not configured",
        )

    try:
        import jwt as pyjwt

        payload = pyjwt.decode(
            body.state,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        nonce = payload.get("nonce")
    except Exception:
        logger.warning("SSO callback: invalid or expired state")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state. Please try signing in again.",
        )

    discovery_url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    with httpx.Client() as client:
        resp = client.get(discovery_url)
        resp.raise_for_status()
        metadata = resp.json()

    token_endpoint = metadata.get("token_endpoint")
    if not token_endpoint:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery failed: no token_endpoint",
        )

    from urllib.parse import urlencode

    auth_response = (
        f"{settings.oidc_redirect_uri}?{urlencode({'code': body.code, 'state': body.state})}"
    )
    oauth_client = OAuth2Client(
        client_id=settings.oidc_client_id,
        client_secret=settings.oidc_client_secret,
        scope="openid profile email",
        redirect_uri=settings.oidc_redirect_uri,
        state=body.state,
    )
    token = oauth_client.fetch_token(
        token_endpoint,
        authorization_response=auth_response,
    )

    id_token = token.get("id_token")
    if not id_token:
        logger.warning("SSO callback: no id_token in response")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="IdP did not return an ID token",
        )

    jwks_uri = metadata.get("jwks_uri")
    if not jwks_uri:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OIDC discovery failed: no jwks_uri",
        )

    import jwt as pyjwt

    with httpx.Client() as client:
        jwks_resp = client.get(jwks_uri)
        jwks_resp.raise_for_status()
        jwks = jwks_resp.json()

    try:
        decoded = pyjwt.decode(
            id_token,
            jwks,
            algorithms=["RS256", "ES256", "HS256"],
            audience=settings.oidc_client_id,
            issuer=settings.oidc_issuer.rstrip("/"),
        )
        if decoded.get("nonce") != nonce:
            raise ValueError("nonce mismatch")
    except Exception as e:
        logger.warning("SSO callback: ID token validation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ID token from identity provider",
        )

    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo_endpoint = metadata.get("userinfo_endpoint")
        if userinfo_endpoint and token.get("access_token"):
            with httpx.Client() as client:
                ui_resp = client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {token['access_token']}"},
                )
                if ui_resp.is_success:
                    userinfo = ui_resp.json()
    if not userinfo:
        userinfo = decoded

    email = userinfo.get("email") or decoded.get("email") or decoded.get("sub")
    if not email or "@" not in str(email):
        logger.warning("SSO callback: no email in userinfo or id_token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Identity provider did not return an email address",
        )

    first_name = userinfo.get("given_name") or userinfo.get("first_name") or ""
    last_name = userinfo.get("family_name") or userinfo.get("last_name") or ""
    name = userinfo.get("name") or ""
    if name and not first_name and not last_name:
        parts = name.split(None, 1)
        first_name = parts[0] if parts else ""
        last_name = parts[1] if len(parts) > 1 else ""

    user = db.query(User).filter(User.email == email).first()
    if user:
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account disabled",
            )
    else:
        slug = _slugify((first_name + " " + last_name).strip() or email.split("@")[0])
        existing_tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if existing_tenant:
            slug = f"{slug}-{uuid.uuid4().hex[:6]}"
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=(first_name + " " + last_name).strip() or email.split("@")[0],
            slug=slug,
        )
        db.add(tenant)
        db.flush()

        placeholder_password = hash_password(secrets.token_hex(32))
        user = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=email,
            hashed_password=placeholder_password,
            first_name=first_name or None,
            last_name=last_name or None,
            role="analyst",
            auth_provider="oidc",
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
            detail={"email": email, "auth_provider": "oidc"},
            ip_address=request.client.host if request.client else None,
        )

    audit_record(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.id,
        action="user.login",
        resource_type="user",
        resource_id=user.id,
        detail={"auth_provider": "oidc"},
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
