"""add agent_builds table

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-25

Adds agent_builds table for storing uploaded agent MSI builds per tenant.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, Sequence[str], None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_builds",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String, nullable=False),
        sa.Column("version", sa.String, nullable=False),
        sa.Column("filename", sa.String, nullable=False),
        sa.Column("file_path", sa.String, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("uploaded_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_agent_builds_tenant_id", "agent_builds", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_builds_tenant_id", table_name="agent_builds")
    op.drop_table("agent_builds")
