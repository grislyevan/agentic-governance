"""add webhook headers for SIEM auth

Revision ID: 0013
Revises: 0012
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, Sequence[str], None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "webhooks",
        sa.Column("headers", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("webhooks", "headers")
