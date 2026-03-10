"""add tenant agent_key_prefix and agent_key_hash columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("agent_key_prefix", sa.String(16), nullable=True))
    op.add_column("tenants", sa.Column("agent_key_hash", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "agent_key_hash")
    op.drop_column("tenants", "agent_key_prefix")
