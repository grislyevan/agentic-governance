"""Application settings loaded from environment / .env file."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_UNSAFE_DEFAULTS = frozenset({
    "dev-secret-change-in-production",
    "change-me",
    "change-me-use-openssl-rand-hex-32",
})


def _default_db_url() -> str:
    """Platform-aware default SQLite path."""
    if sys.platform == "win32":
        data_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec"
    elif sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "Detec"
    else:
        data_dir = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "detec"
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'detec.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (defaults to SQLite; set DATABASE_URL for PostgreSQL)
    database_url: str = ""

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:3001"
    debug: bool = False

    # Binary protocol gateway
    gateway_enabled: bool = True
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8001
    gateway_tls_cert: str = ""
    gateway_tls_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    # Heartbeat
    default_heartbeat_interval: int = 300

    # Webhooks
    webhook_delivery_timeout: int = 10
    webhook_max_retries: int = 3

    # SMTP (for email enrollment; optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    # Seed data (created on first startup if DB is empty)
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change-me"
    seed_tenant_name: str = "Default"

    @model_validator(mode="after")
    def _apply_default_database_url(self) -> "Settings":
        if not self.database_url:
            self.database_url = _default_db_url()
        return self

    @model_validator(mode="after")
    def _reject_unsafe_defaults_in_production(self) -> "Settings":
        env = os.getenv("ENV", "development").lower()
        if env in ("production", "staging"):
            if self.jwt_secret in _UNSAFE_DEFAULTS:
                raise ValueError(
                    "JWT_SECRET must be set to a strong secret in "
                    f"{env} (generate one with: openssl rand -hex 32)"
                )
            if self.seed_admin_password in _UNSAFE_DEFAULTS:
                raise ValueError(
                    "SEED_ADMIN_PASSWORD must be changed from its "
                    f"default value in {env}"
                )
        elif self.jwt_secret in _UNSAFE_DEFAULTS:
            logger.warning(
                "Running with default JWT_SECRET. This is fine for "
                "local development but must be changed before deployment."
            )

        if "*" in self.cors_origins_list:
            if env in ("production", "staging"):
                raise ValueError(
                    "CORS_ORIGINS must not contain '*' in "
                    f"{env}. Use an explicit allowlist of origins."
                )
            logger.warning(
                "CORS_ORIGINS contains '*'. This is unsafe with "
                "allow_credentials=True and must not be used in production."
            )

        return self


settings = Settings()
