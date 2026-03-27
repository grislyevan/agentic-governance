"""add requested_by to approval_requests

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-26
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, Sequence[str], None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("approval_requests") as batch_op:
            batch_op.add_column(sa.Column("requested_by", sa.String(36), nullable=True))
            batch_op.create_foreign_key(
                "fk_approval_requests_requested_by_users",
                "users", ["requested_by"], ["id"], ondelete="SET NULL",
            )
    else:
        op.add_column("approval_requests", sa.Column("requested_by", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_approval_requests_requested_by_users",
            "approval_requests", "users", ["requested_by"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("approval_requests") as batch_op:
            batch_op.drop_constraint("fk_approval_requests_requested_by_users", type_="foreignkey")
            batch_op.drop_column("requested_by")
    else:
        op.drop_constraint("fk_approval_requests_requested_by_users", "approval_requests", type_="foreignkey")
        op.drop_column("approval_requests", "requested_by")
