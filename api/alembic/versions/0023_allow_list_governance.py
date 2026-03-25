"""add governance fields to allow_list_entries

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-24

Adds expires_at, scope, reason_code, and owner_id to allow_list_entries.
Uses batch mode for SQLite (ALTER TABLE on an existing table).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: Union[str, Sequence[str], None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("allow_list_entries") as batch_op:
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column("scope", sa.String(32), nullable=True, server_default="tenant"))
            batch_op.add_column(sa.Column("reason_code", sa.String(64), nullable=True))
            batch_op.add_column(sa.Column("owner_id", sa.String(36), nullable=True))
    else:
        op.add_column("allow_list_entries", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column("allow_list_entries", sa.Column("scope", sa.String(32), nullable=True, server_default="tenant"))
        op.add_column("allow_list_entries", sa.Column("reason_code", sa.String(64), nullable=True))
        op.add_column("allow_list_entries", sa.Column("owner_id", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_allow_list_entries_owner_id_users",
            "allow_list_entries",
            "users",
            ["owner_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("allow_list_entries") as batch_op:
            batch_op.drop_column("owner_id")
            batch_op.drop_column("reason_code")
            batch_op.drop_column("scope")
            batch_op.drop_column("expires_at")
    else:
        op.drop_constraint("fk_allow_list_entries_owner_id_users", "allow_list_entries", type_="foreignkey")
        op.drop_column("allow_list_entries", "owner_id")
        op.drop_column("allow_list_entries", "reason_code")
        op.drop_column("allow_list_entries", "scope")
        op.drop_column("allow_list_entries", "expires_at")
