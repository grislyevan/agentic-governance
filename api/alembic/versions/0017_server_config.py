"""add server_config table for gateway settings

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, Sequence[str], None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "server_config",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("gateway_port", sa.Integer(), nullable=True),
        sa.Column("gateway_host", sa.String(255), nullable=True),
        sa.Column("gateway_enabled", sa.Boolean(), nullable=True),
    )
    op.execute(sa.text("INSERT INTO server_config (id, gateway_port, gateway_host, gateway_enabled) VALUES (1, NULL, NULL, NULL)"))


def downgrade() -> None:
    op.drop_table("server_config")
