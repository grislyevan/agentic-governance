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
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent / "config"
DEFAULT_CONFIG_PATH = CONFIG_DIR / "collector.json"

# Server-pushed state (interval, etc.) persisted so it survives restart.
# Same directory as the agent pid file (~/.agentic-gov).
AGENT_STATE_DIR = Path.home() / ".agentic-gov"
AGENT_STATE_FILE = AGENT_STATE_DIR / "agent_state.json"

ENV_PREFIX = "AGENTIC_GOV_"

# Config keys that must never be logged (secrets).
_SENSITIVE_KEYS = frozenset({"api_key"})

# Keys whose argparse dest names match these config keys.
_ARGPARSE_KEYS = {
    "output", "endpoint_id", "actor_id", "sensitivity",
    "interval", "api_url", "api_key",
    "report_all", "verbose", "dry_run",
    "protocol", "gateway_host", "gateway_port",
    "tcp_connect_timeout_seconds", "tcp_retry_interval_seconds",
    "tcp_failure_threshold", "tcp_recovery_stability_seconds",
    "telemetry_provider",
    "enforcement_posture", "auto_enforce_threshold",
    "allow_linux_uid_block_fallback",
}

_BOOL_KEYS = {"report_all", "verbose", "dry_run", "allow_linux_uid_block_fallback"}
_INT_KEYS = {"interval", "gateway_port", "tcp_failure_threshold"}
_FLOAT_KEYS = {
    "auto_enforce_threshold",
    "tcp_connect_timeout_seconds",
    "tcp_retry_interval_seconds",
    "tcp_recovery_stability_seconds",
}

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
    "protocol":               f"{ENV_PREFIX}PROTOCOL",
    "gateway_host":           f"{ENV_PREFIX}GATEWAY_HOST",
    "gateway_port":           f"{ENV_PREFIX}GATEWAY_PORT",
    "tcp_connect_timeout_seconds": f"{ENV_PREFIX}TCP_CONNECT_TIMEOUT_SECONDS",
    "tcp_retry_interval_seconds": f"{ENV_PREFIX}TCP_RETRY_INTERVAL_SECONDS",
    "tcp_failure_threshold": f"{ENV_PREFIX}TCP_FAILURE_THRESHOLD",
    "tcp_recovery_stability_seconds": f"{ENV_PREFIX}TCP_RECOVERY_STABILITY_SECONDS",
    "telemetry_provider":     f"{ENV_PREFIX}TELEMETRY_PROVIDER",
    "enforcement_posture":    f"{ENV_PREFIX}ENFORCEMENT_POSTURE",
    "auto_enforce_threshold": f"{ENV_PREFIX}AUTO_ENFORCE_THRESHOLD",
    "allow_linux_uid_block_fallback": f"{ENV_PREFIX}ALLOW_LINUX_UID_BLOCK_FALLBACK",
}

SENTINEL_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "probe_interval_ms": 1000,
    "lookback_seconds": 30,
    "observation_window_seconds": 120,
    "trigger_cooldown_seconds": 10,
    "max_alert_scans_per_minute": 4,
    "max_elevations_per_5_minutes": 10,
    "require_corroboration": True,
    "weak_trigger_min_signals": 1,
    "moderate_trigger_min_signals": 2,
    "strong_trigger_min_signals": 3,
}

SENTINEL_ENV_MAP: dict[str, str] = {
    "enabled": f"{ENV_PREFIX}SENTINEL_ENABLED",
    "probe_interval_ms": f"{ENV_PREFIX}SENTINEL_PROBE_INTERVAL_MS",
    "lookback_seconds": f"{ENV_PREFIX}SENTINEL_LOOKBACK_SECONDS",
    "observation_window_seconds": f"{ENV_PREFIX}SENTINEL_OBSERVATION_WINDOW_SECONDS",
    "trigger_cooldown_seconds": f"{ENV_PREFIX}SENTINEL_TRIGGER_COOLDOWN_SECONDS",
    "max_alert_scans_per_minute": f"{ENV_PREFIX}SENTINEL_MAX_ALERT_SCANS_PER_MINUTE",
    "max_elevations_per_5_minutes": f"{ENV_PREFIX}SENTINEL_MAX_ELEVATIONS_PER_5_MINUTES",
    "require_corroboration": f"{ENV_PREFIX}SENTINEL_REQUIRE_CORROBORATION",
    "weak_trigger_min_signals": f"{ENV_PREFIX}SENTINEL_WEAK_TRIGGER_MIN_SIGNALS",
    "moderate_trigger_min_signals": f"{ENV_PREFIX}SENTINEL_MODERATE_TRIGGER_MIN_SIGNALS",
    "strong_trigger_min_signals": f"{ENV_PREFIX}SENTINEL_STRONG_TRIGGER_MIN_SIGNALS",
}

EVENT_STORE_DEFAULTS: dict[str, Any] = {
    "max_events": 10_000,
    "retention_seconds": 120.0,
    "max_events_per_type": None,
    "rate_cap_per_second": 0,
    "burst_window_seconds": 0.1,
    "max_events_per_burst": 0,
}

ENFORCEMENT_DEFAULTS: dict[str, Any] = {
    "protected_parents": [],
    "allow_persistent_disable": False,
    "require_corroboration": True,
}

ENFORCEMENT_ENV_MAP: dict[str, str] = {
    "allow_persistent_disable": f"{ENV_PREFIX}ENFORCEMENT_ALLOW_PERSISTENT_DISABLE",
    "require_corroboration": f"{ENV_PREFIX}ENFORCEMENT_REQUIRE_CORROBORATION",
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
    "protocol": "auto",
    "gateway_host": None,
    "gateway_port": 8001,
    "tcp_connect_timeout_seconds": 3.0,
    "tcp_retry_interval_seconds": 30.0,
    "tcp_failure_threshold": 5,
    "tcp_recovery_stability_seconds": 10.0,
    "telemetry_provider": "auto",
    "enforcement_posture": "passive",
    "auto_enforce_threshold": 0.75,
    "allow_linux_uid_block_fallback": False,
    "sentinel": dict(SENTINEL_DEFAULTS),
    "event_store": dict(EVENT_STORE_DEFAULTS),
    "enforcement": dict(ENFORCEMENT_DEFAULTS),
}


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in ("1", "true", "yes", "on")


def _platform_config_paths() -> list[Path]:
    """Return platform-specific config search paths (highest priority first).

    These are locations where a server-generated installer may drop
    agent.env or collector.json so the agent auto-discovers them.
    On macOS, system-wide config under /Library/Application Support/Detec
    is checked first (used by LaunchDaemon); then per-user ~/Library/...
    """
    paths: list[Path] = []
    if sys.platform == "darwin":
        system_app_support = Path("/Library/Application Support/Detec")
        user_app_support = Path.home() / "Library" / "Application Support" / "Detec"
        # LaunchDaemon runs as root and reads system paths first. Menubar GUI runs as
        # the console user: system agent.env is often mode 600 root-owned, so prefer
        # the user's Application Support copy when not root.
        if os.geteuid() == 0:
            paths.extend(
                [
                    system_app_support / "collector.json",
                    system_app_support / "agent.env",
                    user_app_support / "collector.json",
                    user_app_support / "agent.env",
                ]
            )
        else:
            paths.extend(
                [
                    user_app_support / "collector.json",
                    user_app_support / "agent.env",
                    system_app_support / "collector.json",
                    system_app_support / "agent.env",
                ]
            )
    elif sys.platform == "win32":
        program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec"
        paths.append(program_data / "collector.json")
        # The MSI installs agent.env under Detec\Agent (data dir, separate from binaries).
        paths.append(program_data / "Agent" / "agent.env")
    else:
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        detec_dir = config_home / "detec"
        paths.append(detec_dir / "collector.json")
        paths.append(detec_dir / "agent.env")
    return paths


def _parse_env_file(path: Path) -> dict[str, Any]:
    """Parse a KEY=VALUE env file, ignoring comments and blank lines."""
    result: dict[str, Any] = {}
    try:
        with open(path, encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                if key.startswith(ENV_PREFIX):
                    config_key = key[len(ENV_PREFIX):].lower()
                    if config_key in _BOOL_KEYS:
                        result[config_key] = _parse_bool(value)
                    elif config_key in _INT_KEYS:
                        try:
                            result[config_key] = int(value)
                        except ValueError:
                            pass
                    elif config_key in _FLOAT_KEYS:
                        try:
                            result[config_key] = float(value)
                        except ValueError:
                            pass
                    else:
                        result[config_key] = value
    except OSError as exc:
        logger.debug("Cannot read env file %s: %s", path, exc)
    return result


def load_config_file(path: Path | None = None) -> dict[str, Any]:
    """Load collector JSON config, returning ``{}`` when the file is absent.

    When no explicit *path* is given and the default
    ``collector/config/collector.json`` does not exist, falls back to
    platform-specific search paths (e.g. ~/Library/Application
    Support/Detec/ on macOS).  Both .json and .env files are supported.
    """
    p = path or DEFAULT_CONFIG_PATH
    if p.exists():
        return _load_json_config(p)

    if path is not None:
        return {}

    for candidate in _platform_config_paths():
        if not candidate.exists():
            continue
        if candidate.suffix == ".json":
            cfg = _load_json_config(candidate)
        else:
            cfg = _parse_env_file(candidate)
        if cfg:
            logger.info("Loaded config from platform path: %s", candidate)
            return cfg

    return {}


def _load_json_config(p: Path) -> dict[str, Any]:
    """Load and validate a single JSON config file."""
    try:
        with open(p) as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            logger.warning("Config file %s does not contain a JSON object - ignored", p)
            return {}
        return {k: v for k, v in data.items() if not k.startswith("_") and k != "config_version"}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cannot read config %s: %s", p, exc)
        return {}


def load_server_interval_state() -> dict[str, Any]:
    """Load persisted server-pushed state (e.g. interval_seconds).

    Returns a dict with keys such as interval_seconds, or empty if missing/invalid.
    """
    if not AGENT_STATE_FILE.exists():
        return {}
    try:
        with open(AGENT_STATE_FILE) as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Cannot read agent state %s: %s", AGENT_STATE_FILE, exc)
        return {}


def save_server_interval(interval_seconds: int) -> None:
    """Persist server-desired scan/heartbeat interval so it survives restart.

    Call this when the heartbeat response includes interval_seconds.
    Valid range matches API: 30 to 86400.
    """
    if not (30 <= interval_seconds <= 86400):
        logger.warning("Ignoring out-of-range server interval %s", interval_seconds)
        return
    try:
        AGENT_STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = load_server_interval_state()
        data["interval_seconds"] = interval_seconds
        with open(AGENT_STATE_FILE, "w") as fh:
            json.dump(data, fh, separators=(",", ":"))
        logger.info("Persisted server interval_seconds=%s to %s", interval_seconds, AGENT_STATE_FILE)
    except OSError as exc:
        logger.warning("Could not persist server interval to %s: %s", AGENT_STATE_FILE, exc)


def save_server_behavioral_config(behavioral_config: dict[str, Any]) -> None:
    """Persist server-pushed behavioral threshold overrides.

    Call this when the heartbeat response includes behavioral_config.
    The config is merged on top of file-based defaults at scan time.
    """
    try:
        AGENT_STATE_DIR.mkdir(parents=True, exist_ok=True)
        data = load_server_interval_state()
        data["behavioral_config"] = behavioral_config
        with open(AGENT_STATE_FILE, "w") as fh:
            json.dump(data, fh, separators=(",", ":"))
        logger.info("Persisted server behavioral_config to %s", AGENT_STATE_FILE)
    except OSError as exc:
        logger.warning("Could not persist behavioral_config to %s: %s", AGENT_STATE_FILE, exc)


def load_server_behavioral_config() -> dict[str, Any] | None:
    """Load persisted server-pushed behavioral config overrides.

    Returns the behavioral_config dict, or None if not present.
    """
    state = load_server_interval_state()
    cfg = state.get("behavioral_config")
    if isinstance(cfg, dict):
        return cfg
    return None


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
                log_val = "<redacted>" if key in _SENSITIVE_KEYS else repr(raw)
                logger.warning("Ignoring non-integer value for %s: %s", env_var, log_val)
        elif key in _FLOAT_KEYS:
            try:
                overrides[key] = float(raw)
            except ValueError:
                log_val = "<redacted>" if key in _SENSITIVE_KEYS else repr(raw)
                logger.warning("Ignoring non-float value for %s: %s", env_var, log_val)
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
        if k == "sentinel" and isinstance(v, dict):
            merged["sentinel"] = {**merged.get("sentinel", SENTINEL_DEFAULTS), **v}
        if k == "event_store" and isinstance(v, dict):
            merged["event_store"] = {**merged.get("event_store", EVENT_STORE_DEFAULTS), **v}
        if k == "enforcement" and isinstance(v, dict):
            merged["enforcement"] = {**ENFORCEMENT_DEFAULTS, **v}

    if "gateway_host" not in file_cfg and file_cfg.get("tcp_host"):
        merged["gateway_host"] = str(file_cfg["tcp_host"]).strip()
    if "gateway_port" not in file_cfg and file_cfg.get("tcp_port") is not None:
        try:
            merged["gateway_port"] = int(file_cfg["tcp_port"])
        except (TypeError, ValueError):
            pass

    # Sentinel env overrides
    sentinel = dict(merged.get("sentinel", SENTINEL_DEFAULTS))
    for key, env_var in SENTINEL_ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        if key == "enabled":
            sentinel[key] = _parse_bool(raw)
        elif key in ("probe_interval_ms", "lookback_seconds", "observation_window_seconds",
                     "trigger_cooldown_seconds", "max_alert_scans_per_minute",
                     "max_elevations_per_5_minutes", "weak_trigger_min_signals",
                     "moderate_trigger_min_signals", "strong_trigger_min_signals"):
            try:
                sentinel[key] = int(raw)
            except ValueError:
                logger.warning("Ignoring non-integer value for %s: %s", env_var, repr(raw))
        elif key == "require_corroboration":
            sentinel[key] = _parse_bool(raw)
    merged["sentinel"] = sentinel

    # Enforcement env overrides
    enforcement = dict(merged.get("enforcement", ENFORCEMENT_DEFAULTS))
    for key, env_var in ENFORCEMENT_ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None:
            continue
        if key in ("allow_persistent_disable", "require_corroboration"):
            enforcement[key] = _parse_bool(raw)
    merged["enforcement"] = enforcement

    # Server-pushed interval (persisted from last heartbeat) overrides file default.
    state = load_server_interval_state()
    state_interval = state.get("interval_seconds")
    if isinstance(state_interval, int) and 30 <= state_interval <= 86400:
        merged["interval"] = state_interval

    env_cfg = load_env_overrides()
    for k, v in env_cfg.items():
        if k in merged:
            merged[k] = v

    gh_env = os.environ.get(f"{ENV_PREFIX}TCP_HOST", "").strip()
    if gh_env and not env_cfg.get("gateway_host"):
        merged["gateway_host"] = gh_env
    tp_raw = os.environ.get(f"{ENV_PREFIX}TCP_PORT")
    if tp_raw and not env_cfg.get("gateway_port"):
        try:
            merged["gateway_port"] = int(tp_raw.strip())
        except ValueError:
            pass

    # If api_key still missing, try platform credential store (keychain, Credential Manager, etc.)
    if not merged.get("api_key"):
        try:
            from agent.credentials import get_api_key
            key = get_api_key()
            if key:
                merged["api_key"] = key
        except ImportError:
            logger.debug("Credential store module not available")
        except Exception as e:
            # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
            logger.warning("Credential store lookup failed: %s", e)

    if merged["endpoint_id"] is None:
        merged["endpoint_id"] = socket.gethostname()
    if merged["actor_id"] is None:
        merged["actor_id"] = getpass.getuser()

    return merged


def argparse_defaults(config_path: Path | None = None) -> dict[str, Any]:
    """Return only the keys suitable for ``parser.set_defaults()``."""
    full = load_collector_config(config_path)
    return {k: v for k, v in full.items() if k in _ARGPARSE_KEYS}
