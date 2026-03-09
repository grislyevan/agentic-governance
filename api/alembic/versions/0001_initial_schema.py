"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-08 15:38:02.421445

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(32), nullable=False, server_default="analyst"),
        sa.Column("api_key", sa.String(64), unique=True, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "endpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("hostname", sa.String(255), nullable=False, index=True),
        sa.Column("os_info", sa.String(512), nullable=True),
        sa.Column("posture", sa.String(32), nullable=False, server_default="unmanaged"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("heartbeat_interval", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("signing_public_key", sa.Text(), nullable=True),
        sa.Column("key_fingerprint", sa.String(64), nullable=True, index=True),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("endpoint_id", sa.String(36), sa.ForeignKey("endpoints.id"), nullable=True, index=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_version", sa.String(16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("session_id", sa.String(36), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("parent_event_id", sa.String(36), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("tool_class", sa.String(4), nullable=True),
        sa.Column("tool_version", sa.String(64), nullable=True),
        sa.Column("attribution_confidence", sa.Float(), nullable=True),
        sa.Column("attribution_sources", sa.Text(), nullable=True),
        sa.Column("decision_state", sa.String(32), nullable=True),
        sa.Column("rule_id", sa.String(32), nullable=True),
        sa.Column("severity_level", sa.String(4), nullable=True),
        sa.Column("signature_verified", sa.Boolean(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_events_tenant_observed", "events", ["tenant_id", "observed_at"])
    op.create_index("ix_events_endpoint_type", "events", ["endpoint_id", "event_type"])
    op.create_index("ix_events_tool_name", "events", ["tool_name"])

    op.create_table(
        "policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("rule_id", sa.String(32), nullable=False),
        sa.Column("rule_version", sa.String(16), nullable=False, server_default="0.1.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("actor_id", sa.String(36), nullable=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("policies")
    op.drop_index("ix_events_tool_name", table_name="events")
    op.drop_index("ix_events_endpoint_type", table_name="events")
    op.drop_index("ix_events_tenant_observed", table_name="events")
    op.drop_table("events")
    op.drop_table("endpoints")
    op.drop_table("users")
    op.drop_table("tenants")
