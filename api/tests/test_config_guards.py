"""Tests for production safety guards in api/core/config.py."""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

import pytest

# Ensure api/ is importable
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)


def _set_valid_production_env(monkeypatch, **overrides):
    """Set minimal env vars that pass all production validators.

    Override individual values by passing keyword arguments, e.g.
    ``_set_valid_production_env(monkeypatch, DATABASE_URL="sqlite:///x")``.
    """
    defaults = {
        "ENV": "production",
        "JWT_SECRET": "a" * 64,
        "SEED_ADMIN_PASSWORD": "strong-password-here",
        "ALLOWED_ORIGINS": "https://app.example.com",
        "DATABASE_URL": "postgresql://user:verysecurepassword@localhost/detec",
        "DATABASE_SSLMODE": "require",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)


class TestSQLiteProductionGuard:
    """Verify that SQLite is rejected when ENV=production or staging."""

    def test_sqlite_rejected_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch, DATABASE_URL="sqlite:///tmp/test.db")

        from core.config import Settings

        with pytest.raises(ValueError, match="SQLite is not supported"):
            Settings()

    def test_sqlite_rejected_in_staging(self, monkeypatch):
        _set_valid_production_env(
            monkeypatch,
            ENV="staging",
            DATABASE_URL="sqlite:///tmp/test.db",
            ALLOWED_ORIGINS="https://staging.example.com",
        )

        from core.config import Settings

        with pytest.raises(ValueError, match="SQLite is not supported"):
            Settings()

    def test_sqlite_allowed_in_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")

        from core.config import Settings

        s = Settings()
        assert s.database_url.startswith("sqlite")

    def test_postgresql_allowed_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch)

        from core.config import Settings

        s = Settings()
        assert s.database_url.startswith("postgresql")


class TestENVDetectionHeuristic:
    """P1a: Detect likely-production deployments without explicit ENV."""

    def test_likely_production_without_env_logs_error(self, monkeypatch):
        """Real JWT + 0.0.0.0 (default) + ENV=development -> error log."""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("JWT_SECRET", "a" * 64)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        # API_HOST defaults to 0.0.0.0

        from core.config import Settings

        with patch("core.config.logger") as mock_logger:
            Settings()
        mock_logger.error.assert_called_once()
        assert "ENV is still" in mock_logger.error.call_args[0][0]

    def test_no_warning_when_using_default_jwt(self, monkeypatch):
        """No false positive when JWT is the default (pure dev mode)."""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production")

        from core.config import Settings

        with patch("core.config.logger") as mock_logger:
            Settings()
        # error() should not be called with the ENV heuristic message
        for call in mock_logger.error.call_args_list:
            assert "ENV is still" not in call[0][0]

    def test_no_warning_when_bound_to_localhost(self, monkeypatch):
        """No false positive when bound to localhost (true local dev)."""
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("JWT_SECRET", "a" * 64)
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        monkeypatch.setenv("API_HOST", "127.0.0.1")

        from core.config import Settings

        with patch("core.config.logger") as mock_logger:
            Settings()
        for call in mock_logger.error.call_args_list:
            assert "ENV is still" not in call[0][0]


class TestDatabasePasswordGuard:
    """P1b: Reject weak database passwords in production."""

    def test_weak_db_password_rejected_in_production(self, monkeypatch):
        _set_valid_production_env(
            monkeypatch,
            DATABASE_URL="postgresql://user:change-me@localhost/detec",
        )

        from core.config import Settings

        with pytest.raises(ValueError, match="password is too weak"):
            Settings()

    def test_short_db_password_rejected_in_production(self, monkeypatch):
        _set_valid_production_env(
            monkeypatch,
            DATABASE_URL="postgresql://user:short@localhost/detec",
        )

        from core.config import Settings

        with pytest.raises(ValueError, match="password is too weak"):
            Settings()

    def test_strong_db_password_accepted_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch)

        from core.config import Settings

        Settings()  # should not raise

    def test_weak_db_password_allowed_in_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://user:change-me@localhost/detec"
        )

        from core.config import Settings

        Settings()  # should not raise in dev


class TestDatabaseSSLGuard:
    """P2c: Reject weak SSL modes in production unless overridden."""

    def test_weak_ssl_rejected_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch, DATABASE_SSLMODE="prefer")

        from core.config import Settings

        with pytest.raises(ValueError, match="not safe for"):
            Settings()

    def test_ssl_disable_rejected_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch, DATABASE_SSLMODE="disable")

        from core.config import Settings

        with pytest.raises(ValueError, match="not safe for"):
            Settings()

    def test_weak_ssl_allowed_with_override(self, monkeypatch):
        _set_valid_production_env(
            monkeypatch,
            DATABASE_SSLMODE="prefer",
            DATABASE_SSL_OVERRIDE="allow-insecure",
        )

        from core.config import Settings

        Settings()  # should not raise

    def test_weak_ssl_allowed_in_development(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        monkeypatch.setenv("DATABASE_SSLMODE", "prefer")

        from core.config import Settings

        Settings()  # should not raise

    def test_strong_ssl_accepted_in_production(self, monkeypatch):
        _set_valid_production_env(monkeypatch, DATABASE_SSLMODE="verify-full")

        from core.config import Settings

        Settings()  # should not raise


class TestMetricsTokenWarning:
    """P2a: Warn when METRICS_TOKEN is not set."""

    def test_metrics_token_warning_when_unset(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        monkeypatch.setenv("METRICS_TOKEN", "")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production")

        from core.config import Settings

        with patch("core.config.logger") as mock_logger:
            Settings()
        warn_msgs = [c[0][0] for c in mock_logger.warning.call_args_list]
        assert any("METRICS_TOKEN is not set" in m for m in warn_msgs)

    def test_no_warning_when_metrics_token_set(self, monkeypatch):
        monkeypatch.setenv("ENV", "development")
        monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp/test.db")
        monkeypatch.setenv("METRICS_TOKEN", "some-secret-token")
        monkeypatch.setenv("JWT_SECRET", "dev-secret-change-in-production")

        from core.config import Settings

        with patch("core.config.logger") as mock_logger:
            Settings()
        warn_msgs = [c[0][0] for c in mock_logger.warning.call_args_list]
        assert not any("METRICS_TOKEN is not set" in m for m in warn_msgs)
