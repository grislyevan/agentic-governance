"""add unique constraint on endpoints(tenant_id, hostname)

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-08 16:10:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_endpoints_tenant_hostname", "endpoints", ["tenant_id", "hostname"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_endpoints_tenant_hostname", "endpoints", type_="unique")
