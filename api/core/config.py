"""Application settings loaded from environment / .env file."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_UNSAFE_DEFAULTS = frozenset(
    {
        "dev-secret-change-in-production",
        "change-me",
        "change-me-use-openssl-rand-hex-32",
        "REPLACE_WITH_OPENSSL_RAND_HEX_32",
        "dev-only-not-for-production",
    }
)


def _default_db_url() -> str:
    """Platform-aware default SQLite path."""
    if sys.platform == "win32":
        data_dir = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "Detec"
    elif sys.platform == "darwin":
        data_dir = Path.home() / "Library" / "Application Support" / "Detec"
    else:
        data_dir = (
            Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
            / "detec"
        )
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data_dir / 'detec.db'}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (defaults to SQLite; set DATABASE_URL for PostgreSQL)
    database_url: str = ""
    # PostgreSQL SSL mode. Options:
    #   disable    - no SSL at all
    #   allow      - try non-SSL first, then SSL
    #   prefer     - try SSL first, then non-SSL  (default)
    #   require    - always SSL, but skip CA verification
    #   verify-ca  - always SSL, verify server cert against CA
    #   verify-full - always SSL, verify CA + hostname match
    # Use 'require' or stricter in production.
    database_sslmode: str = "prefer"
    # Set to "allow-insecure" to override the production SSL hard-fail
    # (e.g., for VPC/sidecar proxy topologies with TLS termination at LB).
    database_ssl_override: str = ""

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = (
        "http://localhost:5173,http://localhost:3000,http://localhost:3001"
    )
    allowed_origins: str = ""
    debug: bool = False

    # Self-registration toggle (set ALLOW_REGISTRATION=false to disable)
    allow_registration: bool = True

    # Bearer token for /metrics endpoint (open access when empty)
    metrics_token: str = ""

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

    # Session reports: list and get-by-id use this lookback so list items are fetchable by id
    session_lookback_days: int = 7
    # Max events loaded when resolving a session by id; if more in window, session may 404
    session_report_by_id_event_limit: int = 500

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

    # Default transport in generated agent packages when download omits ?protocol=
    # http: works with Docker exposing only :8000. Use auto or tcp when gateway :8001 is up.
    agent_download_default_protocol: str = "http"

    # Public URL of this server stamped into Windows MSI agent downloads.
    # Empty string means "derive from the Host header of the download request".
    detec_api_url: str = ""

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
    # Comma-separated list of allowed origins for Stripe redirect URLs
    allowed_return_origins: str = ""

    @property
    def stripe_configured(self) -> bool:
        return bool(self.stripe_secret_key and self.stripe_webhook_secret)

    @property
    def allowed_return_origins_list(self) -> list[str]:
        return [s.strip() for s in self.allowed_return_origins.split(",") if s.strip()]

    # SSO / OIDC
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = ""

    @property
    def oidc_configured(self) -> bool:
        return bool(
            self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret
        )

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
            if self.database_url.startswith("sqlite"):
                raise ValueError(
                    f"SQLite is not supported in {env}. "
                    "Set DATABASE_URL to a PostgreSQL connection string "
                    "(e.g. postgresql://user:pass@host:5432/detec)."
                )

            # P1b: Reject weak database passwords in production
            if self.database_url.startswith("postgresql"):
                try:
                    from urllib.parse import urlparse

                    _parsed = urlparse(self.database_url)
                    if _parsed.password and (
                        _parsed.password in _UNSAFE_DEFAULTS
                        or len(_parsed.password) < 12
                    ):
                        raise ValueError(
                            f"DATABASE_URL password is too weak for {env}. "
                            "Use a strong password (12+ characters)."
                        )
                except ValueError:
                    raise
                except Exception:
                    pass  # non-standard URL format; skip check

            if self.database_sslmode in ("disable", "allow", "prefer"):
                if self.database_ssl_override == "allow-insecure":
                    logger.warning(
                        "database_sslmode is '%s' in %s — allowed via "
                        "DATABASE_SSL_OVERRIDE=allow-insecure",
                        self.database_sslmode,
                        env,
                    )
                else:
                    raise ValueError(
                        f"database_sslmode '{self.database_sslmode}' is not "
                        f"safe for {env}. Use 'require', 'verify-ca', or "
                        "'verify-full'. Set DATABASE_SSL_OVERRIDE="
                        "allow-insecure to override (e.g., for VPC/sidecar "
                        "proxy topologies)."
                    )

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

        # P1a: Detect likely-production deployment without explicit ENV
        if env == "development" and self.jwt_secret not in _UNSAFE_DEFAULTS:
            if self.api_host == "0.0.0.0":
                logger.error(
                    "JWT_SECRET is set to a non-default value but ENV is "
                    "still 'development'. If this is a real deployment, "
                    "set ENV=production to enable all production safety "
                    "checks (SSL, CORS, etc.)."
                )

        # P2a: Warn when /metrics is open to unauthenticated access
        if not self.metrics_token:
            logger.warning(
                "METRICS_TOKEN is not set — /metrics endpoint is open to "
                "unauthenticated access. Set METRICS_TOKEN to restrict."
            )

        return self


settings = Settings()
