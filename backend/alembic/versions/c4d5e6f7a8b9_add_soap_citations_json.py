"""add soap_citations_json to summaries

Revision ID: c4d5e6f7a8b9
Revises: 0003_add_embedding_support
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "0003_add_embedding_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column("soap_citations_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("summaries", "soap_citations_json")
