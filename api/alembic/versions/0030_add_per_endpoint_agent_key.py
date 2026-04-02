"""Add per-endpoint agent key columns.

Per-endpoint agent keys allow a single endpoint's key to be rotated
independently without invalidating the whole tenant fleet key.
Three columns are added to the ``endpoints`` table:

- ``agent_key_prefix``  — 8-char prefix used for O(1) candidate lookup
- ``agent_key_hash``    — bcrypt hash of the full key
- ``agent_key_rotated_at`` — UTC timestamp of the last rotation

Revision ID: 0030
Revises:     0029
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("agent_key_prefix", sa.String(16), nullable=True),
    )
    op.add_column(
        "endpoints",
        sa.Column("agent_key_hash", sa.String(128), nullable=True),
    )
    op.add_column(
        "endpoints",
        sa.Column("agent_key_rotated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_endpoints_agent_key_prefix",
        "endpoints",
        ["agent_key_prefix"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_endpoints_agent_key_prefix", table_name="endpoints")
    op.drop_column("endpoints", "agent_key_rotated_at")
    op.drop_column("endpoints", "agent_key_hash")
    op.drop_column("endpoints", "agent_key_prefix")
