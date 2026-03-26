"""add uninstall_token_hash to endpoints

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-26

Adds the uninstall_token_hash column to the endpoints table for tamper
control: stores the SHA-256 hash of a per-endpoint uninstall token so
the server can verify it without persisting the plaintext.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: Union[str, Sequence[str], None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("uninstall_token_hash", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("endpoints", "uninstall_token_hash")
