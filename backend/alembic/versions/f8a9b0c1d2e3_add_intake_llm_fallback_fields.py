"""add intake llm fallback tracking fields

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "intakes",
        sa.Column("llm_fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "intakes",
        sa.Column("llm_error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intakes", "llm_error_message")
    op.drop_column("intakes", "llm_fallback_used")
