"""add refresh_jti column to users for token rotation

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-09 04:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("refresh_jti", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "refresh_jti")
