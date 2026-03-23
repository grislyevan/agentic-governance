"""add tenant agent_key column

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("agent_key", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "agent_key")
