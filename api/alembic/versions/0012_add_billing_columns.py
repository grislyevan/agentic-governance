"""add billing columns to tenants

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-12

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, Sequence[str], None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("stripe_customer_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_tier", sa.String(32), nullable=False, server_default="free"),
    )
    op.add_column(
        "tenants",
        sa.Column("subscription_status", sa.String(32), nullable=False, server_default="active"),
    )
    op.add_column(
        "tenants",
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
    )
    op.create_index("ix_tenants_stripe_customer_id", "tenants", ["stripe_customer_id"])


def downgrade() -> None:
    op.drop_index("ix_tenants_stripe_customer_id", table_name="tenants")
    op.drop_column("tenants", "stripe_subscription_id")
    op.drop_column("tenants", "trial_ends_at")
    op.drop_column("tenants", "subscription_status")
    op.drop_column("tenants", "subscription_tier")
    op.drop_column("tenants", "stripe_customer_id")
