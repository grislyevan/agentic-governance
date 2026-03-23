"""add retention_days column to tenants

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, Sequence[str], None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("retention_days", sa.Integer(), nullable=True, server_default="90"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "retention_days")
