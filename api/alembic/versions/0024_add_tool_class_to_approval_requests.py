"""add tool_class to approval_requests

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-25

Adds tool_class column to approval_requests so the POST /approvals payload
field is persisted rather than silently dropped.
Uses batch mode for SQLite (ALTER TABLE on an existing table).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: Union[str, Sequence[str], None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("approval_requests") as batch_op:
            batch_op.add_column(sa.Column("tool_class", sa.String(64), nullable=True))
    else:
        op.add_column("approval_requests", sa.Column("tool_class", sa.String(64), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("approval_requests") as batch_op:
            batch_op.drop_column("tool_class")
    else:
        op.drop_column("approval_requests", "tool_class")
