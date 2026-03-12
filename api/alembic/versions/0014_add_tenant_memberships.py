"""add tenant_memberships table and seed from existing users

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, Sequence[str], None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="analyst"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenant"),
    )

    conn = op.get_bind()
    users = conn.execute(sa.text("SELECT id, tenant_id, role FROM users")).fetchall()
    for user_id, tenant_id, role in users:
        import uuid
        conn.execute(
            sa.text(
                "INSERT INTO tenant_memberships (id, user_id, tenant_id, role) VALUES (:id, :uid, :tid, :role)"
            ),
            {"id": str(uuid.uuid4()), "uid": user_id, "tid": tenant_id, "role": role},
        )


def downgrade() -> None:
    op.drop_table("tenant_memberships")
