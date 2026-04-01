"""add behavioral_config to endpoint_profiles

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: Union[str, Sequence[str], None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("endpoint_profiles") as batch_op:
            batch_op.add_column(
                sa.Column("behavioral_config", sa.JSON(), nullable=True)
            )
    else:
        op.add_column(
            "endpoint_profiles",
            sa.Column("behavioral_config", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    if is_sqlite:
        with op.batch_alter_table("endpoint_profiles") as batch_op:
            batch_op.drop_column("behavioral_config")
    else:
        op.drop_column("endpoint_profiles", "behavioral_config")
