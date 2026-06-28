"""add embedding support and medical_knowledge table

Revision ID: 0003_add_embedding_support
Revises: b2c3d4e5f6a7
Create Date: 2026-06-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0003_add_embedding_support"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "medical_knowledge" not in inspector.get_table_names():
        op.create_table(
            "medical_knowledge",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.String(length=255), nullable=False),
            sa.Column(
                "chunk_index",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=512), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("embedding", Vector(768), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_medical_knowledge_document_id"),
            "medical_knowledge",
            ["document_id"],
            unique=False,
        )
        op.create_index(
            "ix_medical_knowledge_document_chunk",
            "medical_knowledge",
            ["document_id", "chunk_index"],
            unique=False,
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_medical_knowledge_embedding "
            "ON medical_knowledge USING hnsw (embedding vector_cosine_ops);"
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "medical_knowledge" not in inspector.get_table_names():
        return

    op.execute("DROP INDEX IF EXISTS ix_medical_knowledge_embedding;")
    op.drop_index("ix_medical_knowledge_document_chunk", table_name="medical_knowledge")
    op.drop_index(op.f("ix_medical_knowledge_document_id"), table_name="medical_knowledge")
    op.drop_table("medical_knowledge")
