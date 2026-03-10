"""Agent download router: serve pre-configured agent packages.

Endpoints:
  GET  /agent/download          — Authenticated download (JWT or API key, owner/admin)
  GET  /agent/download/{token}  — Token-based download (unauthenticated, single-use)
  POST /agent/enroll-email      — Send a download link to an end user via email
  GET  /agent/key               — View the tenant agent key prefix
  POST /agent/key/rotate        — Rotate the tenant agent key
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tenant import resolve_auth, require_role
from models.auth_token import AuthToken, hash_token
from models.tenant import Tenant, generate_agent_key
from models.user import User

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/agent", tags=["agent-download"])

_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "dist" / "packages"

_PLATFORM_PACKAGES: dict[str, list[str]] = {
    "macos": ["DetecAgent-latest.pkg", "DetecAgent.pkg"],
    "windows": ["detec-agent.zip"],
    "linux": ["detec-agent-linux.tar.gz"],
}


class Platform(str, Enum):
    macos = "macos"
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
    """Return the tenant's agent key, generating one if it doesn't exist yet."""
    if not tenant.agent_key:
        tenant.agent_key = generate_agent_key()
        db.commit()
        db.refresh(tenant)
        logger.info("Generated agent key for tenant %s (%s)", tenant.name, tenant.id)
    return tenant.agent_key


def _build_agent_env(api_url: str, api_key: str, interval: int, protocol: str,
                     gateway_host: str | None, gateway_port: int) -> str:
    lines = [
        f"AGENTIC_GOV_API_URL={api_url}",
        f"AGENTIC_GOV_API_KEY={api_key}",
        f"AGENTIC_GOV_INTERVAL={interval}",
        f"AGENTIC_GOV_PROTOCOL={protocol}",
    ]
    if protocol == "tcp":
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
    if protocol == "tcp":
        if gateway_host:
            cfg["gateway_host"] = gateway_host
        cfg["gateway_port"] = gateway_port
    return json.dumps(cfg, indent=2) + "\n"


_README_TEMPLATE: dict[str, str] = {
    "macos": """\
# Detec Agent - macOS

## Quick Start

1. Double-click `DetecAgent.pkg` (or the versioned .pkg) to install.
2. The agent is pre-configured to connect to your server automatically.
3. Configuration is placed in `~/Library/Application Support/Detec/`.

If you need to adjust settings later, edit `~/Library/Application Support/Detec/agent.env`
or run `detec-agent setup --api-url ... --api-key ...`.

## Files Included

- `DetecAgent.pkg` (or versioned .pkg) - macOS installer
- `agent.env` - Pre-filled environment config (copy to ~/Library/Application Support/Detec/)
- `collector.json` - Pre-filled JSON config
- This README

## Manual Config Installation

If the installer does not place the config automatically, copy it yourself:

    mkdir -p ~/Library/Application\\ Support/Detec
    cp agent.env ~/Library/Application\\ Support/Detec/agent.env
    cp collector.json ~/Library/Application\\ Support/Detec/collector.json
""",
    "windows": """\
# Detec Agent - Windows

## Quick Start

1. Extract `detec-agent.zip` to `C:\\Program Files\\Detec\\`.
2. The agent is pre-configured to connect to your server automatically.
3. From an elevated prompt, install and start the service:

       cd "C:\\Program Files\\Detec\\detec-agent"
       .\\detec-agent.exe install
       .\\detec-agent.exe start

## Files Included

- `detec-agent.zip` - Windows agent distribution
- `collector.json` - Pre-filled JSON config (copy to %PROGRAMDATA%\\Detec\\)
- `agent.env` - Pre-filled environment config (alternative)
- This README

## Manual Config Installation

If the installer does not place the config automatically:

    mkdir %PROGRAMDATA%\\Detec
    copy collector.json %PROGRAMDATA%\\Detec\\collector.json
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


def _build_zip(pkg_path: Path, api_url: str, api_key: str, interval: int,
               protocol: str, gateway_host: str | None, platform: str) -> io.BytesIO:
    """Build the agent zip bundle with config files baked in."""
    env_content = _build_agent_env(
        api_url=api_url, api_key=api_key, interval=interval, protocol=protocol,
        gateway_host=gateway_host, gateway_port=settings.gateway_port,
    )
    json_content = _build_collector_json(
        api_url=api_url, api_key=api_key, interval=interval, protocol=protocol,
        gateway_host=gateway_host, gateway_port=settings.gateway_port,
    )
    readme = _README_TEMPLATE.get(platform, "")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pkg_path, pkg_path.name)
        zf.writestr("agent.env", env_content)
        zf.writestr("collector.json", json_content)
        if readme:
            zf.writestr("README.md", readme)
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Authenticated download (dashboard / admin)
# ---------------------------------------------------------------------------

@router.get("/download")
@limiter.limit("10/minute")
def download_agent(
    request: Request,
    platform: Platform = Query(..., description="Target platform"),
    interval: int = Query(default=300, ge=30, le=86400, description="Scan interval in seconds"),
    protocol: Literal["http", "tcp"] = Query(default="http", description="Transport protocol"),
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

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
    gateway_host = request.base_url.hostname if protocol == "tcp" else None

    buf = _build_zip(pkg_path, api_url, agent_key, interval, protocol, gateway_host, platform.value)

    filename = f"detec-agent-{platform.value}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
    protocol: Literal["http", "tcp"] = Query(default="http"),
    db: Session = Depends(get_db),
) -> StreamingResponse:
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
    gateway_host = request.base_url.hostname if protocol == "tcp" else None

    db.commit()

    buf = _build_zip(pkg_path, api_url, agent_key, interval, protocol, gateway_host, platform.value)

    filename = f"detec-agent-{platform.value}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# Email enrollment
# ---------------------------------------------------------------------------

class EnrollEmailRequest(BaseModel):
    email: EmailStr
    platform: Platform
    interval: int = Field(default=300, ge=30, le=86400)
    protocol: Literal["http", "tcp"] = "http"


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
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> EnrollEmailResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    from core.email import send_email, EmailNotConfiguredError

    token_obj, raw_token = AuthToken.create_download_token(auth.user_id)
    db.add(token_obj)

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    _ensure_agent_key(tenant, db)

    base_url = str(request.base_url).rstrip("/")
    params = f"platform={body.platform.value}&interval={body.interval}&protocol={body.protocol}"
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
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> AgentKeyResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant or not tenant.agent_key:
        return AgentKeyResponse(key_prefix="", has_key=False)

    return AgentKeyResponse(
        key_prefix=tenant.agent_key[:8],
        has_key=True,
    )


@router.post("/key/rotate", response_model=AgentKeyRotateResponse)
@limiter.limit("5/minute")
def rotate_agent_key(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None),
) -> AgentKeyRotateResponse:
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Tenant not found")

    tenant.agent_key = generate_agent_key()

    from core.audit_logger import record as audit_record
    audit_record(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action="agent.key_rotated",
        resource_type="tenant",
        resource_id=tenant.id,
        detail={"new_key_prefix": tenant.agent_key[:8]},
        ip_address=request.client.host if request.client else None,
    )
    db.commit()
    db.refresh(tenant)

    return AgentKeyRotateResponse(
        agent_key=tenant.agent_key,
        message="Agent key rotated. Existing agents using the old key will need to be reconfigured.",
    )
