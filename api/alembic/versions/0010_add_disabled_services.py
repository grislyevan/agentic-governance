"""add disabled_services and pending_restore_services columns to endpoints

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, Sequence[str], None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("disabled_services", sa.JSON(), nullable=True),
    )
    op.add_column(
        "endpoints",
        sa.Column("pending_restore_services", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("endpoints", "pending_restore_services")
    op.drop_column("endpoints", "disabled_services")
