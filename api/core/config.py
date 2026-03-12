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
    allowed_origins: str = ""
    debug: bool = False

    # Binary protocol gateway
    gateway_enabled: bool = True
    gateway_host: str = "0.0.0.0"
    gateway_port: int = 8001
    gateway_tls_cert: str = ""
    gateway_tls_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        env = os.getenv("ENV", "development").lower()
        if env in ("production", "staging"):
            origins = self.allowed_origins
            if not origins:
                return []
            return [s.strip() for s in origins.split(",") if s.strip()]
        return [s.strip() for s in self.cors_origins.split(",") if s.strip()]

    # Enforcement
    default_enforcement_posture: str = "passive"
    default_auto_enforce_threshold: float = 0.75

    # Heartbeat
    default_heartbeat_interval: int = 300

    # Retention and privacy
    default_retention_days: int = 90
    stale_threshold_days: int = 30

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

    # Demo mode: seeds realistic sample data on startup
    demo_mode: bool = False

    # Seed data (created on first startup if DB is empty)
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "change-me"
    seed_tenant_name: str = "Default"
    seed_api_key: str = ""
    seed_agent_key: str = ""

    # EDR Integration
    edr_provider: str = ""
    edr_api_base: str = ""
    edr_client_id: str = ""
    edr_client_secret: str = ""
    edr_enrichment_enabled: bool = False
    edr_query_window_before_seconds: int = 300
    edr_query_window_after_seconds: int = 60

    @property
    def edr_configured(self) -> bool:
        return bool(
            self.edr_provider
            and self.edr_api_base
            and self.edr_client_id
            and self.edr_client_secret
        )

    # EDR Enforcement (delegated enforcement via EDR/MDM tools)
    edr_enforcement_enabled: bool = False
    edr_enforcement_fallback: str = "local"

    @property
    def edr_enforcement_configured(self) -> bool:
        return self.edr_enforcement_enabled and self.edr_configured

    # Jamf Pro (macOS MDM enforcement)
    jamf_url: str = ""
    jamf_client_id: str = ""
    jamf_client_secret: str = ""

    @property
    def jamf_configured(self) -> bool:
        return bool(self.jamf_url and self.jamf_client_id and self.jamf_client_secret)

    # Microsoft Intune (Windows MDM enforcement)
    intune_tenant_id: str = ""
    intune_client_id: str = ""
    intune_client_secret: str = ""

    @property
    def intune_configured(self) -> bool:
        return bool(
            self.intune_tenant_id
            and self.intune_client_id
            and self.intune_client_secret
        )

    # Stripe Billing
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    stripe_price_id_enterprise: str = ""

    @property
    def stripe_configured(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)

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

        if env in ("production", "staging"):
            origins = [s.strip() for s in self.allowed_origins.split(",") if s.strip()]
            if not origins:
                raise ValueError(
                    f"ALLOWED_ORIGINS must be set in {env}. "
                    "Provide a comma-separated list of allowed dashboard origins."
                )
            if "*" in origins:
                raise ValueError(
                    "ALLOWED_ORIGINS must not contain '*' in "
                    f"{env}. Use an explicit allowlist of origins."
                )
        elif "*" in self.cors_origins_list:
            logger.warning(
                "CORS_ORIGINS contains '*'. This is unsafe with "
                "allow_credentials=True and must not be used in production."
            )

        return self


settings = Settings()
