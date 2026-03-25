"""Agent download router: serve pre-configured agent packages.

Endpoints:
  GET  /agent/download          — Authenticated download (JWT or API key, owner/admin)
  GET  /agent/download/{token}  — Token-based download (unauthenticated, single-use)
  POST /agent/enroll-email      — Send a download link to an end user via email
  GET  /agent/key               — View the tenant agent key prefix
  POST /agent/key/rotate        — Rotate the tenant agent key
"""

import io
import json
import logging
import os
import struct
import sys
import zipfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.config import settings
from core.server_config import get_effective_gateway_config
from core.database import get_db
from core.auth_cookies import get_authorization
from core.tenant import resolve_auth, require_role, generate_agent_key
from models.auth_token import AuthToken, hash_token
from models.tenant import Tenant
from models.user import User

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

Proto = Literal["auto", "http", "tcp"]


def _effective_protocol(requested: str | None) -> Proto:
    """Resolve transport: explicit query/body wins; else AGENT_DOWNLOAD_DEFAULT_PROTOCOL."""
    raw = (requested or settings.agent_download_default_protocol or "http").strip().lower()
    if raw in ("auto", "http", "tcp"):
        return raw  # type: ignore[return-value]
    logger.warning("Invalid agent_download_default_protocol %r; using http", raw)
    return "http"

router = APIRouter(prefix="/agent", tags=["agent-download"])

if getattr(sys, "frozen", False):
    _APP_ROOT = Path(sys.executable).resolve().parent
else:
    _APP_ROOT = Path(__file__).resolve().parent.parent.parent

_dist_override = os.environ.get("AGENT_PACKAGES_DIR")
_DIST_DIR = Path(_dist_override) if _dist_override else _APP_ROOT / "dist" / "packages"

_PLATFORM_PACKAGES: dict[str, list[str]] = {
    "windows": ["DetecAgentSetup.exe", "detec-agent.zip"],
    "linux": ["detec-agent-linux.tar.gz"],
}

_CFG_MAGIC = b"DETEC_CFG_V1\x00"


class Platform(str, Enum):
    windows = "windows"
    linux = "linux"


def _find_package(platform: str) -> Path | None:
    """Locate the pre-built installer for *platform* in dist/packages/."""
    candidates = _PLATFORM_PACKAGES.get(platform, [])
    for name in candidates:
        p = _DIST_DIR / name
        if p.is_file():
            return p
    return None


def _ensure_agent_key(tenant: Tenant, db: Session) -> str:
    """Return the tenant's agent key (full key), generating one if it doesn't exist yet.

    For tenants already on the new hash-based scheme (agent_key_hash is set),
    this cannot return the full key — callers that need the full key should use
    the rotate endpoint instead.  For new tenants with no key at all, we generate
    a hashed key and return the full key once.
    """
    if tenant.agent_key_hash:
        # Key exists in hashed form; full key is not stored. Return a placeholder
        # so download endpoints can still function — agents received the full key
        # at rotation time.  Downloads will embed the prefix only as a hint.
        # Callers that truly need the raw key must rotate.
        return tenant.agent_key_prefix or ""
    if not tenant.agent_key:
        # No key at all — generate a new hashed key
        full_key, prefix, key_hash = generate_agent_key()
        tenant.agent_key_prefix = prefix
        tenant.agent_key_hash = key_hash
        tenant.agent_key = None
        db.commit()
        db.refresh(tenant)
        logger.info("Generated agent key for tenant %s (%s)", tenant.name, tenant.id)
        return full_key
    # Legacy plaintext key — return as-is until rotated
    return tenant.agent_key


def _build_agent_env(api_url: str, api_key: str, interval: int, protocol: str,
                     gateway_host: str | None, gateway_port: int) -> str:
    lines = [
        f"AGENTIC_GOV_API_URL={api_url}",
        f"AGENTIC_GOV_API_KEY={api_key}",
        f"AGENTIC_GOV_INTERVAL={interval}",
        f"AGENTIC_GOV_PROTOCOL={protocol}",
    ]
    if protocol in ("tcp", "auto"):
        if gateway_host:
            lines.append(f"AGENTIC_GOV_GATEWAY_HOST={gateway_host}")
        lines.append(f"AGENTIC_GOV_GATEWAY_PORT={gateway_port}")
    return "\n".join(lines) + "\n"


def _build_collector_json(api_url: str, api_key: str, interval: int, protocol: str,
                          gateway_host: str | None, gateway_port: int) -> str:
    cfg: dict = {
        "api_url": api_url,
        "api_key": api_key,
        "interval": interval,
        "protocol": protocol,
    }
    if protocol in ("tcp", "auto"):
        if gateway_host:
            cfg["gateway_host"] = gateway_host
        cfg["gateway_port"] = gateway_port
    return json.dumps(cfg, indent=2) + "\n"


_README_TEMPLATE: dict[str, str] = {
    "windows": """\
# Detec Agent - Windows

This zip contains the installer and pre-filled configuration. No manual setup needed.

## Quick Start

1. Extract this zip to a folder (e.g. Desktop or Downloads).
2. Run `DetecAgentSetup.exe` from that folder (right-click, Run as administrator).
3. The installer applies the config from the extracted files and installs the agent. The agent connects to your server automatically.

Config files (`agent.env`, `collector.json`) must stay in the same folder as the installer when you run it so the installer can apply them.

## Silent install

From an elevated command prompt:

    DetecAgentSetup.exe /VERYSILENT

To also launch the system tray after install: `DetecAgentSetup.exe /VERYSILENT /LAUNCHTRAY=1`

## Files Included

- `DetecAgentSetup.exe` - Windows installer (do not modify; run from same folder as config)
- `agent.env` - Pre-filled server config
- `collector.json` - Pre-filled JSON config
- This README
""",
    "linux": """\
# Detec Agent - Linux

## Quick Start

1. Extract `detec-agent-linux.tar.gz`.
2. The agent is pre-configured to connect to your server automatically.
3. Copy the config and start the agent:

       mkdir -p ~/.config/detec
       cp agent.env ~/.config/detec/agent.env
       cp collector.json ~/.config/detec/collector.json
       ./detec-agent --interval 300

## Files Included

- `detec-agent-linux.tar.gz` - Linux agent distribution
- `agent.env` - Pre-filled environment config
- `collector.json` - Pre-filled JSON config
- This README

## Systemd Service

To run as a persistent service:

    mkdir -p ~/.config/systemd/user
    cp detec-agent.service ~/.config/systemd/user/
    systemctl --user daemon-reload
    systemctl --user enable --now detec-agent.service
""",
}


def _derive_api_url(request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/api"


def _embed_config_in_exe(exe_bytes: bytes, api_url: str, api_key: str,
                         interval: int, protocol: str,
                         gateway_host: str | None, gateway_port: int) -> bytes:
    """Append a config payload to an installer EXE.

    Layout appended after the original PE data::

        [DETEC_CFG_V1\\0] [JSON bytes] [4-byte LE length] [DETEC_CFG_V1\\0]

    The Inno Setup installer's post-install step reads this from the end
    of its own executable to extract tenant configuration.
    """
    cfg: dict = {
        "api_url": api_url,
        "api_key": api_key,
        "interval": interval,
        "protocol": protocol,
    }
    if protocol in ("tcp", "auto"):
        if gateway_host:
            cfg["gateway_host"] = gateway_host
        cfg["gateway_port"] = gateway_port
    json_bytes = json.dumps(cfg, indent=2).encode("utf-8")
    payload = _CFG_MAGIC + json_bytes + struct.pack("<I", len(json_bytes)) + _CFG_MAGIC
    return exe_bytes + payload


def _build_zip(pkg_path: Path, api_url: str, api_key: str, interval: int,
               protocol: str, gateway_host: str | None, gateway_port: int,
               platform: str) -> io.BytesIO:
    """Build the agent zip bundle with config files baked in."""
    env_content = _build_agent_env(
        api_url=api_url, api_key=api_key, interval=interval, protocol=protocol,
        gateway_host=gateway_host, gateway_port=gateway_port,
    )
    json_content = _build_collector_json(
        api_url=api_url, api_key=api_key, interval=interval, protocol=protocol,
        gateway_host=gateway_host, gateway_port=gateway_port,
    )
    readme = _README_TEMPLATE.get(platform, "")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Store the installer as-is; it's already compressed (.pkg/.zip/.tar.gz)
        # and re-deflating wastes minutes of CPU for zero size savings.
        zf.write(pkg_path, pkg_path.name, compress_type=zipfile.ZIP_STORED)
        zf.writestr("agent.env", env_content)
        zf.writestr("collector.json", json_content)
        if readme:
            zf.writestr("README.md", readme)
    buf.seek(0)
    return buf


def _build_download_response(
    pkg_path: Path, api_url: str, api_key: str, interval: int,
    protocol: str, gateway_host: str | None, gateway_port: int, platform: str,
) -> Response:
    """Build the appropriate download response for the given package.

    All platforms (including Windows) are served as a zip containing the
    installer plus agent.env and collector.json. The Windows installer
    reads config from the same directory as the EXE, so no EXE modification
    is needed (enables code signing and avoids AV false positives).
    """
    buf = _build_zip(pkg_path, api_url, api_key, interval, protocol, gateway_host, gateway_port, platform)
    content = buf.getvalue()
    filename = f"detec-agent-{platform}.zip"
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(content)),
        },
    )


# ---------------------------------------------------------------------------
# Authenticated download (dashboard / admin)
# ---------------------------------------------------------------------------

@router.get("/download")
@limiter.limit("10/minute")
def download_agent(
    request: Request,
    platform: Platform = Query(..., description="Target platform"),
    interval: int = Query(default=300, ge=30, le=86400, description="Scan interval in seconds"),
    protocol: Proto | None = Query(
        default=None,
        description="Transport: omit for server default (http), or auto, tcp, http",
    ),
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Depends(get_authorization),
) -> Response:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    eff_protocol = _effective_protocol(protocol)

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Tenant not found")

    agent_key = _ensure_agent_key(tenant, db)

    pkg_path = _find_package(platform.value)
    if pkg_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No pre-built agent package found for '{platform.value}'. "
                f"Place the installer in {_DIST_DIR}/ "
                f"(expected: {', '.join(_PLATFORM_PACKAGES[platform.value])})."
            ),
        )

    api_url = _derive_api_url(request)
    gateway_host = (
        request.base_url.hostname if eff_protocol in ("tcp", "auto") else None
    )
    gw_cfg = get_effective_gateway_config(db)

    return _build_download_response(
        pkg_path, api_url, agent_key, interval, eff_protocol, gateway_host, gw_cfg.port, platform.value,
    )


# ---------------------------------------------------------------------------
# Token-based download (unauthenticated, single-use link from email)
# ---------------------------------------------------------------------------

@router.get("/download/{token}")
@limiter.limit("10/minute")
def download_agent_by_token(
    request: Request,
    token: str,
    platform: Platform = Query(..., description="Target platform"),
    interval: int = Query(default=300, ge=30, le=86400),
    protocol: Proto | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Response:
    eff_protocol = _effective_protocol(protocol)
    token_hash = hash_token(token)
    token_obj = db.query(AuthToken).filter(
        AuthToken.token_hash == token_hash,
        AuthToken.purpose == "agent_download",
    ).first()

    if not token_obj or not token_obj.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired download link. Please request a new one from your administrator.",
        )

    token_obj.used_at = datetime.now(timezone.utc)

    admin = db.query(User).filter(User.id == token_obj.user_id).first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid download link.")

    tenant = db.query(Tenant).filter(Tenant.id == admin.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Tenant not found")

    agent_key = _ensure_agent_key(tenant, db)

    pkg_path = _find_package(platform.value)
    if pkg_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pre-built agent package available for '{platform.value}'.",
        )

    api_url = _derive_api_url(request)
    gateway_host = (
        request.base_url.hostname if eff_protocol in ("tcp", "auto") else None
    )
    gw_cfg = get_effective_gateway_config(db)

    db.commit()

    return _build_download_response(
        pkg_path, api_url, agent_key, interval, eff_protocol, gateway_host, gw_cfg.port, platform.value,
    )


# ---------------------------------------------------------------------------
# Email enrollment
# ---------------------------------------------------------------------------

class EnrollEmailRequest(BaseModel):
    email: EmailStr
    platform: Platform
    interval: int = Field(default=300, ge=30, le=86400)
    protocol: Proto | None = None


# Explicitly provide the types namespace so Pydantic v2 can resolve `Platform`
# and `Proto` if the model is rebuilt (e.g., during FastAPI startup with
# deferred annotation evaluation).
EnrollEmailRequest.model_rebuild(_types_namespace={"Platform": Platform, "Proto": Proto})


class EnrollEmailResponse(BaseModel):
    status: str
    email: str
    expires_in_hours: int


@router.post("/enroll-email", response_model=EnrollEmailResponse)
@limiter.limit("20/minute")
def enroll_email(
    request: Request,
    body: EnrollEmailRequest,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> EnrollEmailResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    from core.email import send_email, EmailNotConfiguredError

    token_obj, raw_token = AuthToken.create_download_token(auth.user_id)
    db.add(token_obj)

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    _ensure_agent_key(tenant, db)

    eff_protocol = _effective_protocol(body.protocol)
    base_url = str(request.base_url).rstrip("/")
    params = f"platform={body.platform.value}&interval={body.interval}&protocol={eff_protocol}"
    download_url = f"{base_url}/api/agent/download/{raw_token}?{params}"

    subject = "Install the Detec Agent on your machine"
    html_body = f"""\
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
  <h2 style="color: #1a1a2e;">Detec Agent Installation</h2>
  <p>Your IT team has enrolled your machine in Detec endpoint monitoring.</p>
  <p>Click the button below to download a pre-configured agent package for <strong>{body.platform.value}</strong>.
     After installing, the agent will connect automatically.</p>
  <p style="margin: 24px 0;">
    <a href="{download_url}"
       style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px;
              border-radius: 8px; text-decoration: none; font-weight: 600;">
      Download Detec Agent
    </a>
  </p>
  <p style="color: #666; font-size: 13px;">
    This link expires in 72 hours and can only be used once.<br>
    If you did not expect this email, you can safely ignore it.
  </p>
</div>
"""
    text_body = (
        f"Your IT team has enrolled your machine in Detec endpoint monitoring.\n\n"
        f"Download the pre-configured agent for {body.platform.value}:\n{download_url}\n\n"
        f"This link expires in 72 hours and can only be used once."
    )

    try:
        send_email(body.email, subject, html_body, text_body)
    except EmailNotConfiguredError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email delivery is not configured. Set SMTP_HOST and SMTP_FROM in the server environment.",
        )
    except Exception:
        db.rollback()
        logger.exception("Failed to send enrollment email to %s", body.email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send email. Check SMTP configuration.",
        )

    from core.audit_logger import record as audit_record
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="agent.enroll_email",
        resource_type="agent_download",
        resource_id=token_obj.id,
        detail={"email": body.email, "platform": body.platform.value},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()

    return EnrollEmailResponse(
        status="sent",
        email=body.email,
        expires_in_hours=72,
    )


# ---------------------------------------------------------------------------
# Tenant agent key management
# ---------------------------------------------------------------------------

class AgentKeyResponse(BaseModel):
    key_prefix: str
    has_key: bool


class AgentKeyRotateResponse(BaseModel):
    agent_key: str
    message: str


@router.get("/key", response_model=AgentKeyResponse)
def get_agent_key(
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> AgentKeyResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        return AgentKeyResponse(key_prefix="", has_key=False)

    # Prefer the new hashed fields; fall back to legacy plaintext key
    if tenant.agent_key_prefix:
        return AgentKeyResponse(key_prefix=tenant.agent_key_prefix, has_key=True)
    if tenant.agent_key:
        return AgentKeyResponse(key_prefix=tenant.agent_key[:8], has_key=True)
    return AgentKeyResponse(key_prefix="", has_key=False)


@router.post("/key/rotate", response_model=AgentKeyRotateResponse)
@limiter.limit("5/minute")
def rotate_agent_key(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
) -> AgentKeyRotateResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Tenant not found")

    full_key, prefix, key_hash = generate_agent_key()
    tenant.agent_key_prefix = prefix
    tenant.agent_key_hash = key_hash
    tenant.agent_key = None  # clear plaintext; full key shown once below

    from core.audit_logger import record as audit_record
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="agent.key_rotated",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"new_key_prefix": prefix},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(tenant)

    return AgentKeyRotateResponse(
        agent_key=full_key,
        message="Agent key rotated. Existing agents using the old key will need to be reconfigured.",
    )
