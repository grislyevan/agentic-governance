"""add telemetry_provider column to endpoints

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("telemetry_provider", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("endpoints", "telemetry_provider")
