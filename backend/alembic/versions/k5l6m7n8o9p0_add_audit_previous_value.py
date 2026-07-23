"""add previous_value to audit_logs

Revision ID: k5l6m7n8o9p0
Revises: j4k5l6m7n8o9
Create Date: 2026-07-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k5l6m7n8o9p0"
down_revision: Union[str, None] = "j4k5l6m7n8o9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("previous_value", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audit_logs", "previous_value")
