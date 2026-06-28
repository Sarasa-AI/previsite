"""rename file columns for s3 storage

Revision ID: b2c3d4e5f6a7
Revises: 0002_enable_pgvector
Create Date: 2026-06-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "0002_enable_pgvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("files", "file_path", new_column_name="s3_key")
    op.alter_column("files", "file_size", new_column_name="size_bytes")
    op.alter_column("files", "mime_type", new_column_name="content_type")


def downgrade() -> None:
    op.alter_column("files", "s3_key", new_column_name="file_path")
    op.alter_column("files", "size_bytes", new_column_name="file_size")
    op.alter_column("files", "content_type", new_column_name="mime_type")
