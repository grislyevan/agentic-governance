"""add approval_requests table

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-24

Tracks approval_required policy decisions so analysts/admins can approve or
deny them.  Uses op.create_table() for both dialects since this is a new
table (no ALTER TABLE / batch mode required).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: Union[str, Sequence[str], None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=False),
        sa.Column("endpoint_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("confidence_band", sa.String(16), nullable=True),
        sa.Column("confidence_score", sa.Float, nullable=True),
        sa.Column("policy_rule_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("requester_type", sa.String(16), nullable=False, server_default="agent"),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.String(1024), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_approval_requests_tenant_id_tenants",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"],
            ["endpoints.id"],
            name="fk_approval_requests_endpoint_id_endpoints",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name="fk_approval_requests_decided_by_users",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_table("approval_requests")
