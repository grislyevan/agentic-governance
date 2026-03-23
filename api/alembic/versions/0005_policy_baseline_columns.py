"""add is_baseline and category columns to policies

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "policies",
        sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "policies",
        sa.Column("category", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("policies", "category")
    op.drop_column("policies", "is_baseline")
