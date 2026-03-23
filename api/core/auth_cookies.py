"""Cookie-based auth: names, options, and dependency to resolve token from cookie."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Request

COOKIE_ACCESS = "detec_access_token"
COOKIE_REFRESH = "detec_refresh_token"


def _cookie_options(secure: bool, same_site: str = "lax") -> dict:
    return {
        "httponly": True,
        "secure": secure,
        "samesite": same_site,
        "path": "/",
        "max_age": None,
    }


def cookie_options_access(secure: bool | None = None) -> dict:
    if secure is None:
        env = os.getenv("ENV", "development").lower()
        secure = env in ("production", "staging")
    opts = _cookie_options(secure=secure)
    # Short-lived; browser sends on every request
    opts["max_age"] = 60 * 60  # 1 hour
    return opts


def cookie_options_refresh(secure: bool | None = None) -> dict:
    if secure is None:
        env = os.getenv("ENV", "development").lower()
        secure = env in ("production", "staging")
    opts = _cookie_options(secure=secure)
    opts["max_age"] = 30 * 24 * 60 * 60  # 30 days
    return opts


def get_authorization(request: Request) -> str | None:
    """Return Authorization value from header or from access-token cookie (for browser)."""
    auth = request.headers.get("Authorization")
    if auth and auth.strip().lower().startswith("bearer "):
        return auth
    token = request.cookies.get(COOKIE_ACCESS)
    if token:
        return "".join(("Bearer ", token))
    return None
