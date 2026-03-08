"""Centralized configuration for the collector.

Precedence (highest wins):
    CLI flags  >  environment variables (AGENTIC_GOV_*)  >  config file  >  code defaults

The config file is optional.  When absent the collector behaves exactly as
before — CLI flags and hardcoded defaults drive everything.
"""

from __future__ import annotations

import getpass
import json
import logging
import os
import socket
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "collector.json"

ENV_PREFIX = "AGENTIC_GOV_"

# Keys whose argparse dest names match these config keys.
_ARGPARSE_KEYS = {
    "output", "endpoint_id", "actor_id", "sensitivity",
    "interval", "api_url", "api_key",
    "report_all", "verbose", "dry_run",
}

_BOOL_KEYS = {"report_all", "verbose", "dry_run"}
_INT_KEYS = {"interval"}

# Map config key → environment variable name.
ENV_MAP: dict[str, str] = {
    "output":                 f"{ENV_PREFIX}OUTPUT",
    "endpoint_id":            f"{ENV_PREFIX}ENDPOINT_ID",
    "actor_id":               f"{ENV_PREFIX}ACTOR_ID",
    "sensitivity":            f"{ENV_PREFIX}SENSITIVITY",
    "network_allowlist_path": f"{ENV_PREFIX}NETWORK_ALLOWLIST_PATH",
    "interval":               f"{ENV_PREFIX}INTERVAL",
    "api_url":                f"{ENV_PREFIX}API_URL",
    "api_key":                f"{ENV_PREFIX}API_KEY",
    "report_all":             f"{ENV_PREFIX}REPORT_ALL",
    "verbose":                f"{ENV_PREFIX}VERBOSE",
    "dry_run":                f"{ENV_PREFIX}DRY_RUN",
}

CODE_DEFAULTS: dict[str, Any] = {
    "output": "./scan-results.ndjson",
    "endpoint_id": None,
    "actor_id": None,
    "sensitivity": "Tier0",
    "network_allowlist_path": None,
    "interval": 0,
    "api_url": None,
    "api_key": None,
    "report_all": False,
    "verbose": False,
    "dry_run": False,
}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    """Load collector JSON config, returning ``{}`` when the file is absent."""
    p = path or DEFAULT_CONFIG_PATH
    if not p.exists():
        return {}
    try:
        with open(p) as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("Config file %s does not contain a JSON object — ignored", p)
            return {}
        return {k: v for k, v in data.items() if not k.startswith("_") and k != "config_version"}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read config %s: %s", p, exc)
        return {}


def load_env_overrides() -> dict[str, Any]:
    """Read ``AGENTIC_GOV_*`` environment variables and coerce types."""
    overrides: dict[str, Any] = {}
    for key, env_var in ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        if key in _BOOL_KEYS:
            overrides[key] = _parse_bool(raw)
        elif key in _INT_KEYS:
            try:
                overrides[key] = int(raw)
            except ValueError:
                logger.warning("Ignoring non-integer value for %s: %r", env_var, raw)
        else:
            overrides[key] = raw
    return overrides


def load_collector_config(config_path: Path | None = None) -> dict[str, Any]:
    """Merge code defaults ← config file ← env vars and return the result.

    The returned dict uses the same key names as argparse dest attributes
    (``endpoint_id``, ``dry_run``, etc.) so it can be passed directly to
    ``parser.set_defaults()``.
    """
    merged = dict(CODE_DEFAULTS)

    file_cfg = load_config_file(config_path)
    for k, v in file_cfg.items():
        if k in merged and v is not None:
            merged[k] = v

    env_cfg = load_env_overrides()
    for k, v in env_cfg.items():
        if k in merged:
            merged[k] = v

    # If api_key still missing, try platform credential store (keychain, Credential Manager, etc.)
    if not merged.get("api_key"):
        try:
            from agent.credentials import get_api_key
            key = get_api_key()
            if key:
                merged["api_key"] = key
        except Exception as e:
            logger.debug("Credential store lookup skipped: %s", e)

    if merged["endpoint_id"] is None:
        merged["endpoint_id"] = socket.gethostname()
    if merged["actor_id"] is None:
        merged["actor_id"] = getpass.getuser()

    return merged


def argparse_defaults(config_path: Path | None = None) -> dict[str, Any]:
    """Return only the keys suitable for ``parser.set_defaults()``."""
    full = load_collector_config(config_path)
    return {k: v for k, v in full.items() if k in _ARGPARSE_KEYS}
