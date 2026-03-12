"""rename posture to management_state on endpoints

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-11

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "endpoints",
        "posture",
        new_column_name="management_state",
    )


def downgrade() -> None:
    op.alter_column(
        "endpoints",
        "management_state",
        new_column_name="posture",
    )
