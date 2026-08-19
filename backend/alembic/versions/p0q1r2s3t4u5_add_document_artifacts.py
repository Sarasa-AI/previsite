"""add document_artifacts table

Introduces the missing artifact stage between an uploaded File and any clinical
fact derived from it:

    File → DocumentArtifact(kind='ocr') → DocumentArtifact(kind='extraction')

The extraction payload carries per-value provenance (page, bounding box, verbatim
source text, engine confidence, method) so every value rendered in the Doctor
Workspace is traceable to its source document.

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "p0q1r2s3t4u5"
down_revision: Union[str, None] = "o9p0q1r2s3t4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_artifacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=False, server_default=""),
        sa.Column(
            "engine_version", sa.String(length=64), nullable=False, server_default=""
        ),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_artifacts_id", "document_artifacts", ["id"])
    op.create_index(
        "ix_document_artifacts_session_id", "document_artifacts", ["session_id"]
    )
    op.create_index("ix_document_artifacts_file_id", "document_artifacts", ["file_id"])
    op.create_index("ix_document_artifacts_kind", "document_artifacts", ["kind"])
    op.create_index(
        "ix_document_artifacts_file_kind", "document_artifacts", ["file_id", "kind"]
    )
    op.create_index(
        "ix_document_artifacts_session_kind",
        "document_artifacts",
        ["session_id", "kind"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_artifacts_session_kind", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_file_kind", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_kind", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_file_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_session_id", table_name="document_artifacts")
    op.drop_index("ix_document_artifacts_id", table_name="document_artifacts")
    op.drop_table("document_artifacts")
