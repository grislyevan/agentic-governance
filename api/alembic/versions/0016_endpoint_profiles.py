"""add endpoint_profiles table and endpoint_profile_id on endpoints

Revision ID: 0016
Revises: 0015
Create Date: 2026-03-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, Sequence[str], None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "endpoint_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "scan_interval_seconds",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("300"),
        ),
        sa.Column(
            "enforcement_posture",
            sa.String(16),
            nullable=False,
            server_default=sa.text("'passive'"),
        ),
        sa.Column(
            "auto_enforce_threshold",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.75"),
        ),
        sa.Column("policy_set_id", sa.String(128), nullable=True),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_endpoint_profiles_tenant_slug"),
    )

    op.add_column(
        "endpoints",
        sa.Column("endpoint_profile_id", sa.String(36), nullable=True, index=True),
    )


def downgrade() -> None:
    op.drop_column("endpoints", "endpoint_profile_id")
    op.drop_table("endpoint_profiles")
