"""fix event_id unique constraint to be scoped per tenant

Previously event_id had a global unique constraint, meaning two different
tenants could not submit events with the same event_id. This replaces it
with a composite unique constraint on (tenant_id, event_id).

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect as sa_inspect

revision: str = "0018"
down_revision: Union[str, Sequence[str], None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        # SQLite requires a full table rebuild to change constraints.
        # Dynamically find the anonymous unique constraint on event_id so we
        # can drop it by name inside batch mode.
        inspector = sa_inspect(bind)
        unique_constraints = inspector.get_unique_constraints("events")
        old_constraint_name = None
        for uc in unique_constraints:
            if uc["column_names"] == ["event_id"]:
                old_constraint_name = uc["name"]
                break

        with op.batch_alter_table("events", recreate="always") as batch_op:
            if old_constraint_name:
                batch_op.drop_constraint(old_constraint_name, type_="unique")
            batch_op.create_unique_constraint(
                "uq_events_tenant_event_id", ["tenant_id", "event_id"]
            )
    else:
        # PostgreSQL: drop the single-column unique constraint (name follows
        # SQLAlchemy's default convention: <table>_<column>_key) and replace
        # it with the composite one.
        op.drop_constraint("events_event_id_key", "events", type_="unique")
        op.create_unique_constraint(
            "uq_events_tenant_event_id", "events", ["tenant_id", "event_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("events", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_events_tenant_event_id", type_="unique")
            batch_op.create_unique_constraint("events_event_id_key", "events", ["event_id"])
    else:
        op.drop_constraint("uq_events_tenant_event_id", "events", type_="unique")
        op.create_unique_constraint("events_event_id_key", "events", ["event_id"])
