"""add EDR enforcement delegation columns to endpoints

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("edr_host_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "endpoints",
        sa.Column("enforcement_provider", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("endpoints", "enforcement_provider")
    op.drop_column("endpoints", "edr_host_id")
