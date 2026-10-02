"""P1 schema reconciliation: intakes, is_hpi_complete, PENDING_REVIEW, audit indexes

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-10-02

Idempotent reconciliation so empty-DB and create_all-seeded DBs both converge
on the current ORM models without failing or duplicating objects.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q1r2s3t4u5v6"
down_revision: Union[str, None] = "p0q1r2s3t4u5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def _column_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def _index_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    tables = _table_names(bind)

    # ── intakes table (full model shape) ─────────────────────────────────
    if "intakes" not in tables:
        op.create_table(
            "intakes",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("session_id", sa.Integer(), nullable=False),
            sa.Column("current_layer", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("demographics_json", sa.Text(), nullable=True),
            sa.Column("hpi_questions_json", sa.Text(), nullable=True),
            sa.Column("hpi_answers_json", sa.Text(), nullable=True),
            sa.Column("question_strategy", sa.Text(), nullable=True),
            sa.Column("clinical_summary_json", sa.Text(), nullable=True),
            sa.Column("medical_history_json", sa.Text(), nullable=True),
            sa.Column(
                "llm_fallback_used",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
            sa.Column("llm_error_message", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=True,
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("session_id"),
        )
        op.create_index(op.f("ix_intakes_id"), "intakes", ["id"], unique=False)
    else:
        cols = _column_names(bind, "intakes")
        for name, col in (
            ("current_layer", sa.Column("current_layer", sa.Integer(), nullable=False, server_default="1")),
            ("demographics_json", sa.Column("demographics_json", sa.Text(), nullable=True)),
            ("hpi_questions_json", sa.Column("hpi_questions_json", sa.Text(), nullable=True)),
            ("hpi_answers_json", sa.Column("hpi_answers_json", sa.Text(), nullable=True)),
            ("question_strategy", sa.Column("question_strategy", sa.Text(), nullable=True)),
            ("clinical_summary_json", sa.Column("clinical_summary_json", sa.Text(), nullable=True)),
            ("medical_history_json", sa.Column("medical_history_json", sa.Text(), nullable=True)),
            (
                "llm_fallback_used",
                sa.Column(
                    "llm_fallback_used",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            ),
            ("llm_error_message", sa.Column("llm_error_message", sa.Text(), nullable=True)),
            (
                "created_at",
                sa.Column(
                    "created_at",
                    sa.DateTime(timezone=True),
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                    nullable=True,
                ),
            ),
            ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)),
        ):
            if name not in cols:
                op.add_column("intakes", col)

        indexes = _index_names(bind, "intakes")
        if "ix_intakes_id" not in indexes:
            op.create_index(op.f("ix_intakes_id"), "intakes", ["id"], unique=False)

    # ── summaries.is_hpi_complete ────────────────────────────────────────
    if "summaries" in tables:
        cols = _column_names(bind, "summaries")
        if "is_hpi_complete" not in cols:
            if dialect == "postgresql":
                op.execute(
                    "ALTER TABLE summaries ADD COLUMN IF NOT EXISTS "
                    "is_hpi_complete BOOLEAN DEFAULT FALSE"
                )
            else:
                op.add_column(
                    "summaries",
                    sa.Column(
                        "is_hpi_complete",
                        sa.Boolean(),
                        nullable=True,
                        server_default=sa.false(),
                    ),
                )

    # ── sessionstatus enum: PENDING_REVIEW ───────────────────────────────
    # PostgreSQL cannot ADD VALUE inside a transaction block on older versions;
    # Alembic's autocommit_block is the correct mechanism. Label casing matches
    # 0001_initial_schema (ACTIVE/COMPLETED/CANCELLED member names).
    if dialect == "postgresql":
        with op.get_context().autocommit_block():
            op.execute(
                """
                DO $$ BEGIN
                    ALTER TYPE sessionstatus ADD VALUE IF NOT EXISTS 'PENDING_REVIEW';
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                    WHEN undefined_object THEN NULL;
                END $$;
                """
            )

    # ── audit_logs composite indexes (no FK on user_id) ──────────────────
    if "audit_logs" in tables:
        indexes = _index_names(bind, "audit_logs")
        if "ix_audit_logs_user_id_timestamp" not in indexes:
            op.create_index(
                "ix_audit_logs_user_id_timestamp",
                "audit_logs",
                ["user_id", "timestamp"],
                unique=False,
            )
        if "ix_audit_logs_resource_type_resource_id" not in indexes:
            op.create_index(
                "ix_audit_logs_resource_type_resource_id",
                "audit_logs",
                ["resource_type", "resource_id"],
                unique=False,
            )


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    tables = _table_names(bind)

    if "audit_logs" in tables:
        indexes = _index_names(bind, "audit_logs")
        if "ix_audit_logs_resource_type_resource_id" in indexes:
            op.drop_index(
                "ix_audit_logs_resource_type_resource_id",
                table_name="audit_logs",
            )
        if "ix_audit_logs_user_id_timestamp" in indexes:
            op.drop_index(
                "ix_audit_logs_user_id_timestamp",
                table_name="audit_logs",
            )

    if "summaries" in tables:
        cols = _column_names(bind, "summaries")
        if "is_hpi_complete" in cols:
            op.drop_column("summaries", "is_hpi_complete")

    # Enum values cannot be safely removed on PostgreSQL; leave PENDING_REVIEW.
    _ = dialect
