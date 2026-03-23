"""hash tenant agent keys using prefix+SHA-256 pattern

Add agent_key_prefix and agent_key_hash columns to the tenants table,
and migrate existing plaintext agent_key values to hashed storage.
The agent_key column is retained (NULLed out) for the migration period
and can be dropped in a future revision.

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-22

"""

from typing import Sequence, Union
import hashlib

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, Sequence[str], None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("tenants") as batch_op:
            batch_op.add_column(sa.Column("agent_key_prefix", sa.String(16), nullable=True))
            batch_op.add_column(sa.Column("agent_key_hash", sa.String(128), nullable=True))
    else:
        op.add_column("tenants", sa.Column("agent_key_prefix", sa.String(16), nullable=True))
        op.add_column("tenants", sa.Column("agent_key_hash", sa.String(128), nullable=True))

    # Create index on agent_key_prefix for fast prefix-based lookups
    op.create_index("ix_tenants_agent_key_prefix", "tenants", ["agent_key_prefix"])

    # Data migration: hash existing plaintext agent keys in-place
    tenants_table = sa.table(
        "tenants",
        sa.column("id", sa.String),
        sa.column("agent_key", sa.String),
        sa.column("agent_key_prefix", sa.String),
        sa.column("agent_key_hash", sa.String),
    )
    rows = bind.execute(
        sa.select(tenants_table.c.id, tenants_table.c.agent_key).where(
            tenants_table.c.agent_key.isnot(None)
        )
    ).fetchall()

    for row in rows:
        tenant_id, raw_key = row
        prefix = raw_key[:8]
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        bind.execute(
            tenants_table.update()
            .where(tenants_table.c.id == tenant_id)
            .values(agent_key_prefix=prefix, agent_key_hash=key_hash, agent_key=None)
        )


def downgrade() -> None:
    op.drop_index("ix_tenants_agent_key_prefix", table_name="tenants")

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("tenants") as batch_op:
            batch_op.drop_column("agent_key_hash")
            batch_op.drop_column("agent_key_prefix")
    else:
        op.drop_column("tenants", "agent_key_hash")
        op.drop_column("tenants", "agent_key_prefix")
