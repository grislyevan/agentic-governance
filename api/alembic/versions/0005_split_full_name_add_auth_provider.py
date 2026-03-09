"""split full_name into first/last, add auth_provider and password_reset_required

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-09 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_name", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(128), nullable=True))
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(32), nullable=False, server_default="local"),
    )
    op.add_column(
        "users",
        sa.Column(
            "password_reset_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, full_name FROM users WHERE full_name IS NOT NULL")
    ).fetchall()
    for user_id, full_name in rows:
        parts = full_name.strip().split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else None
        conn.execute(
            sa.text("UPDATE users SET first_name = :first, last_name = :last WHERE id = :id"),
            {"first": first, "last": last, "id": user_id},
        )

    op.drop_column("users", "full_name")


def downgrade() -> None:
    op.add_column("users", sa.Column("full_name", sa.String(255), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users SET full_name = TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, ''))"
        )
    )

    op.drop_column("users", "password_reset_required")
    op.drop_column("users", "auth_provider")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
