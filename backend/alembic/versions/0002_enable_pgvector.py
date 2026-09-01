"""enable pgvector extension

Revision ID: 0002_enable_pgvector
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0002_enable_pgvector"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from alembic import op
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    from alembic import op
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS vector;")
