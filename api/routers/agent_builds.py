"""Agent build upload and listing.

POST /api/agent-builds — upload a base MSI (admin/owner only)
GET  /api/agent-builds — list uploaded builds (admin/owner only)
"""

from __future__ import annotations

import hashlib
import os

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from core.auth_cookies import get_authorization
from core.database import get_db
from core.tenant import require_role, resolve_auth, strict_tenant_filter
from models.agent_build import AgentBuild

router = APIRouter(prefix="/agent-builds", tags=["agent-builds"])

DATA_DIR = os.environ.get(
    "DETEC_DATA_DIR",
    os.path.join(os.environ.get("PROGRAMDATA", "/tmp"), "Detec"),
)
BUILDS_DIR = os.path.join(DATA_DIR, "agent-builds")


@router.post("", status_code=201)
async def upload_agent_build(
    file: UploadFile = File(...),
    version: str = Form(...),
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Upload a new agent MSI build. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    content = await file.read()
    sha256 = hashlib.sha256(content).hexdigest()

    version_dir = os.path.join(BUILDS_DIR, auth.tenant_id, version)
    os.makedirs(version_dir, exist_ok=True)
    file_path = os.path.join(version_dir, "DetecAgent.msi")

    with open(file_path, "wb") as f:
        f.write(content)

    build = AgentBuild(
        tenant_id=auth.tenant_id,
        version=version,
        filename=file.filename or "DetecAgent.msi",
        file_path=file_path,
        sha256=sha256,
    )
    db.add(build)
    db.commit()
    db.refresh(build)

    return {
        "id": build.id,
        "version": build.version,
        "sha256": build.sha256,
        "uploaded_at": build.uploaded_at.isoformat(),
    }


@router.get("")
async def list_agent_builds(
    authorization: str | None = Depends(get_authorization),
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """List uploaded agent builds for the tenant. Requires admin or owner role."""
    auth = resolve_auth(authorization, x_api_key, db)
    require_role(auth, "owner", "admin")

    builds = (
        db.query(AgentBuild)
        .filter(strict_tenant_filter(auth, AgentBuild))
        .order_by(AgentBuild.uploaded_at.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "version": b.version,
            "sha256": b.sha256,
            "uploaded_at": b.uploaded_at.isoformat(),
        }
        for b in builds
    ]
