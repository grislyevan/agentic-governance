"""Database migrations and seed on startup."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from core.auth import hash_password
from core.config import settings
from core.database import SessionLocal, engine
from models import Tenant, User
from models.user import API_KEY_PREFIX_LEN, generate_api_key, hash_api_key

import logging

logger = logging.getLogger("agentic_governance")

_API_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def apply_migrations() -> None:
    """Run Alembic migrations on startup, falling back to create_all."""
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
    except Exception:
        logger.warning(
            "Alembic migration failed; falling back to create_all",
            exc_info=True,
        )

    from core.database import Base
    import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


def seed() -> None:
    """Seed a default admin user and tenant on first startup."""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == settings.seed_admin_email).first()
        if existing:
            return

        from models.tenant import generate_agent_key

        slug = settings.seed_tenant_name.lower().replace(" ", "-")[:64]
        agent_key = settings.seed_agent_key or generate_agent_key()
        tenant = Tenant(
            id=str(uuid.uuid4()),
            name=settings.seed_tenant_name,
            slug=slug,
            agent_key=agent_key,
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

        n_endpoints = 0
        n_events = 0
        if settings.demo_mode:
            from core.demo_seed import seed_demo_data
            n_endpoints, n_events = seed_demo_data(db, tenant.id)

        db.commit()
        logger.info(
            "Seed: created tenant '%s', admin '%s', and %d baseline policies",
            tenant.name, admin.email, n_policies,
        )
        if settings.demo_mode:
            logger.info(
                "Demo mode: seeded %d endpoints and %d events",
                n_endpoints, n_events,
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
