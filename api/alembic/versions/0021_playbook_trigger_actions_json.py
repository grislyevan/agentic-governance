"""migrate ResponsePlaybook trigger and actions from Text to JSON

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-22

No data migration is required: the stored values are already valid JSON
strings.  SQLAlchemy's JSON type on SQLite continues to use TEXT under the
hood, so this is a logical-type change only for that dialect.  On PostgreSQL
the TEXT -> JSON cast is implicit for well-formed JSON.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, Sequence[str], None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("response_playbooks") as batch_op:
        batch_op.alter_column(
            "trigger",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "actions",
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("response_playbooks") as batch_op:
        batch_op.alter_column(
            "trigger",
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "actions",
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=False,
        )
