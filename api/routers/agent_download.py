"""Agent download router: serve pre-configured agent packages.

Admins and owners can download a zip bundle containing the platform
installer, a pre-filled agent.env/collector.json, and a README. The
agent connects to this server automatically after install with zero
manual configuration.
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from enum import Enum
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.tenant import resolve_auth, require_role

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


def _build_agent_env(api_url: str, api_key: str, interval: int, protocol: str,
                     gateway_host: str | None, gateway_port: int) -> str:
    """Generate agent.env contents (KEY=VALUE format)."""
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
    """Generate collector.json contents."""
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
    """Derive the server's external API URL from the incoming request."""
    base = str(request.base_url).rstrip("/")
    return f"{base}/api"


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

    raw_api_key = x_api_key
    if not raw_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Api-Key header is required for agent downloads (the key is embedded in the package).",
        )

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

    gateway_host: str | None = None
    if protocol == "tcp":
        gateway_host = request.base_url.hostname

    env_content = _build_agent_env(
        api_url=api_url,
        api_key=raw_api_key,
        interval=interval,
        protocol=protocol,
        gateway_host=gateway_host,
        gateway_port=settings.gateway_port,
    )

    json_content = _build_collector_json(
        api_url=api_url,
        api_key=raw_api_key,
        interval=interval,
        protocol=protocol,
        gateway_host=gateway_host,
        gateway_port=settings.gateway_port,
    )

    readme = _README_TEMPLATE.get(platform.value, "")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pkg_path, pkg_path.name)
        zf.writestr("agent.env", env_content)
        zf.writestr("collector.json", json_content)
        if readme:
            zf.writestr("README.md", readme)
    buf.seek(0)

    filename = f"detec-agent-{platform.value}.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
