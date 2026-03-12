"""add enforcement posture columns and allow_list_entries table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "endpoints",
        sa.Column("enforcement_posture", sa.String(16), nullable=False, server_default=sa.text("'passive'")),
    )
    op.add_column(
        "endpoints",
        sa.Column("auto_enforce_threshold", sa.Float(), nullable=False, server_default=sa.text("0.75")),
    )

    op.create_table(
        "allow_list_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("pattern", sa.String(512), nullable=False),
        sa.Column("pattern_type", sa.String(16), nullable=False, server_default=sa.text("'name'")),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tenant_id", "pattern", "pattern_type", name="uq_allow_list_tenant_pattern_type"),
    )


def downgrade() -> None:
    op.drop_table("allow_list_entries")
    op.drop_column("endpoints", "auto_enforce_threshold")
    op.drop_column("endpoints", "enforcement_posture")
