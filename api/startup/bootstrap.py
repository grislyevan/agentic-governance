"""Database migrations and seed on startup."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import sqlalchemy as sa
from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal, engine
from models import Tenant, User
from models.user import API_KEY_PREFIX_LEN, generate_api_key, hash_api_key

import logging

logger = logging.getLogger("agentic_governance")

_API_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def apply_migrations() -> None:
    """Run Alembic migrations on startup, falling back to create_all.

    In production/staging, migration failures are fatal — the server will
    not start with a potentially drifted schema.  In development, the
    original create_all fallback is preserved for convenience.
    """
    env = os.getenv("ENV", "development").lower()
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command

        ini_path = _API_DIR / "alembic.ini"
        if ini_path.exists():
            cfg = AlembicConfig(str(ini_path))
            cfg.set_main_option("sqlalchemy.url", settings.database_url)
            alembic_command.upgrade(cfg, "head")
            logger.info("Alembic migrations applied successfully")
            return
        # alembic.ini not found — fall through to create_all
        logger.info("alembic.ini not found; using create_all")
    except ImportError:
        # Alembic not installed (expected in packaged / PyInstaller builds)
        logger.info("Alembic not installed; using create_all")
    except Exception:
        if env in ("production", "staging"):
            logger.error(
                "Alembic migration failed in %s — refusing to fall back "
                "to create_all. Fix the migration or set ENV=development.",
                env,
                exc_info=True,
            )
            raise
        logger.warning(
            "Alembic migration failed; falling back to create_all",
            exc_info=True,
        )

    from core.database import Base
    import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def warn_unhashed_agent_keys() -> None:
    """Log a warning if any tenants still have un-hashed agent keys.

    This is a non-blocking check -- the server starts regardless, but
    operators are alerted so they can rotate keys before those tenants
    are locked out (the legacy plaintext auth fallback has been removed).
    """
    db = SessionLocal()
    try:
        count = (
            db.query(sa.func.count(Tenant.id))
            .filter(Tenant.agent_key_hash.is_(None))
            .scalar()
        )
        if count:
            logger.warning(
                "%d tenant(s) have un-hashed agent keys and cannot authenticate. "
                "Run key rotation to fix: POST /api/agent/key/rotate",
                count,
            )
    except Exception:
        logger.debug("Could not check for un-hashed agent keys", exc_info=True)
    finally:
        db.close()


def seed() -> None:
    """Seed a default admin user and tenant on first startup."""
    db = SessionLocal()
    try:
        existing = (
            db.query(User)
            .filter(sa.func.lower(User.email) == settings.seed_admin_email.lower())
            .first()
        )
        if existing:
            return

        from core.tenant import generate_agent_key

        slug = settings.seed_tenant_name.lower().replace(" ", "-")[:64]
        if settings.seed_agent_key:
            from core.tenant import _hash_agent_key, AGENT_KEY_PREFIX_LEN

            agent_key = settings.seed_agent_key
            agent_key_prefix = agent_key[:AGENT_KEY_PREFIX_LEN]
            agent_key_hash = _hash_agent_key(agent_key)
        else:
            agent_key, agent_key_prefix, agent_key_hash = generate_agent_key()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=settings.seed_tenant_name,
            slug=slug,
            agent_key=agent_key,
            agent_key_prefix=agent_key_prefix,
            agent_key_hash=agent_key_hash,
        )
        db.add(tenant)
        db.flush()

        if settings.seed_api_key:
            raw_key = settings.seed_api_key
            prefix = raw_key[:API_KEY_PREFIX_LEN]
            key_hash = hash_api_key(raw_key)
        else:
            raw_key, prefix, key_hash = generate_api_key()
        admin = User(
            id=str(uuid.uuid4()),
            tenant_id=tenant.id,
            email=settings.seed_admin_email,
            hashed_password=hash_password(settings.seed_admin_password),
            first_name="Admin",
            role="owner",
            api_key_prefix=prefix,
            api_key_hash=key_hash,
        )
        db.add(admin)
        db.flush()

        from core.baseline_policies import seed_baseline_policies

        n_policies = seed_baseline_policies(db, tenant.id)

        db.commit()
        logger.info(
            "Seed: created tenant '%s', admin '%s', and %d baseline policies",
            tenant.name,
            admin.email,
            n_policies,
        )
        # Print credentials once to stdout. Never write to disk in cwd.
        print(
            "\nInitial admin credentials (store securely; they will not be shown again):\n"
            f"  username: {admin.email}\n"
            f"  password: (set via SEED_ADMIN_PASSWORD)\n"
            f"  admin_api_key: {raw_key}\n"
            f"  agent_key: {agent_key}\n",
            flush=True,
        )
        # nosemgrep: python.lang.security.audit.logging.logger-credential-leak.python-logger-credential-disclosure
        logger.info(
            "[seed] Admin API key prefix: %s... (full key printed above)",
            raw_key[:8],
        )
        logger.info("[seed] Tenant agent key prefix: %s...", agent_key[:8])
    except Exception:
        db.rollback()
        logger.warning("Seed skipped (set DEBUG=true for details)")
        logger.debug("Seed error details", exc_info=True)
    finally:
        db.close()
