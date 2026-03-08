"""hash api keys at rest

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-08 16:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("api_key_prefix", sa.String(8), index=True))
    op.add_column("users", sa.Column("api_key_hash", sa.String(64), unique=True))

    # Migrate existing plaintext keys to hashed form
    conn = op.get_bind()
    users = conn.execute(
        sa.text("SELECT id, api_key FROM users WHERE api_key IS NOT NULL")
    ).fetchall()
    if users:
        import hashlib
        for user_id, raw_key in users:
            prefix = raw_key[:8]
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
            conn.execute(
                sa.text(
                    "UPDATE users SET api_key_prefix = :prefix, api_key_hash = :hash WHERE id = :id"
                ),
                {"prefix": prefix, "hash": key_hash, "id": user_id},
            )

    op.drop_index("ix_users_api_key", table_name="users")
    op.drop_column("users", "api_key")


def downgrade() -> None:
    op.add_column("users", sa.Column("api_key", sa.String(64), unique=True))
    op.create_index("ix_users_api_key", "users", ["api_key"])
    op.drop_column("users", "api_key_hash")
    op.drop_index("ix_users_api_key_prefix", table_name="users")
    op.drop_column("users", "api_key_prefix")
