"""add cascade deletes for tenant/endpoint child tables

Revision ID: 0020
Revises: 0019
Create Date: 2026-03-22

Drop and recreate FK constraints on child tables with ON DELETE CASCADE
(or ON DELETE SET NULL for the nullable endpoint_id on events).

Tables covered:
  - events.tenant_id          -> tenants.id  CASCADE
  - events.endpoint_id        -> endpoints.id SET NULL
  - endpoints.tenant_id       -> tenants.id  CASCADE
  - users.tenant_id           -> tenants.id  CASCADE
  - tenant_memberships.tenant_id -> tenants.id CASCADE

SQLite does not support ALTER TABLE ... ADD/DROP CONSTRAINT for FK changes;
those dialects use batch_alter_table to rebuild the table.  PostgreSQL drops
and recreates the named constraints explicitly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, Sequence[str], None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helper: (table, column, referred_table, ondelete, constraint_name)
# ---------------------------------------------------------------------------
_CASCADE_FKS = [
    ("events",            "tenant_id",  "tenants",   "CASCADE",  "fk_events_tenant_id_tenants"),
    ("endpoints",         "tenant_id",  "tenants",   "CASCADE",  "fk_endpoints_tenant_id_tenants"),
    ("users",             "tenant_id",  "tenants",   "CASCADE",  "fk_users_tenant_id_tenants"),
    ("tenant_memberships","tenant_id",  "tenants",   "CASCADE",  "fk_tenant_memberships_tenant_id_tenants"),
]

_SET_NULL_FKS = [
    ("events", "endpoint_id", "endpoints", "SET NULL", "fk_events_endpoint_id_endpoints"),
]


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        # SQLite: rebuild each table via batch mode; the new ForeignKey
        # definitions come from the batch_alter_table recreate.
        with op.batch_alter_table("events", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_events_tenant_id_tenants",   type_="foreignkey")
            batch_op.drop_constraint("fk_events_endpoint_id_endpoints", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_events_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
                ondelete="CASCADE",
            )
            batch_op.create_foreign_key(
                "fk_events_endpoint_id_endpoints",
                "endpoints", ["endpoint_id"], ["id"],
                ondelete="SET NULL",
            )

        with op.batch_alter_table("endpoints", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_endpoints_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_endpoints_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
                ondelete="CASCADE",
            )

        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_users_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_users_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
                ondelete="CASCADE",
            )

        with op.batch_alter_table("tenant_memberships", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_tenant_memberships_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_tenant_memberships_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
                ondelete="CASCADE",
            )

    else:
        # PostgreSQL (and other ANSI dialects): drop by name then recreate.
        for table, col, ref_table, ondelete, name in _CASCADE_FKS + _SET_NULL_FKS:
            op.drop_constraint(name, table, type_="foreignkey")
            op.create_foreign_key(
                name,
                table, ref_table,
                [col], ["id"],
                ondelete=ondelete,
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("events", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_events_tenant_id_tenants",     type_="foreignkey")
            batch_op.drop_constraint("fk_events_endpoint_id_endpoints",  type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_events_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
            )
            batch_op.create_foreign_key(
                "fk_events_endpoint_id_endpoints",
                "endpoints", ["endpoint_id"], ["id"],
            )

        with op.batch_alter_table("endpoints", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_endpoints_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_endpoints_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
            )

        with op.batch_alter_table("users", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_users_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_users_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
            )

        with op.batch_alter_table("tenant_memberships", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_tenant_memberships_tenant_id_tenants", type_="foreignkey")
            batch_op.create_foreign_key(
                "fk_tenant_memberships_tenant_id_tenants",
                "tenants", ["tenant_id"], ["id"],
            )

    else:
        for table, col, ref_table, _ondelete, name in _CASCADE_FKS + _SET_NULL_FKS:
            op.drop_constraint(name, table, type_="foreignkey")
            op.create_foreign_key(
                name,
                table, ref_table,
                [col], ["id"],
            )
