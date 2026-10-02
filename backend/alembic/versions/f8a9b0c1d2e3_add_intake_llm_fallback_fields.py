"""add intake llm fallback tracking fields

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-06-28

NOTE (P1): This historical revision is edited to be self-sufficient and
idempotent. On a fresh database the intakes table was never created by any
earlier revision, so `op.add_column("intakes", ...)` failed. Creating the
table here (existence-guarded) allows `alembic upgrade head` on an empty DB
to succeed without rewriting the entire chain. Editing history is acceptable
only because the change is idempotent for databases that already have intakes.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8a9b0c1d2e3"
down_revision: Union[str, None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def _column_names(bind, table: str) -> set[str]:
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = _table_names(bind)

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
        if "llm_fallback_used" not in cols:
            op.add_column(
                "intakes",
                sa.Column(
                    "llm_fallback_used",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )
        if "llm_error_message" not in cols:
            op.add_column(
                "intakes",
                sa.Column("llm_error_message", sa.Text(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    cols = _column_names(bind, "intakes")
    if "llm_error_message" in cols:
        op.drop_column("intakes", "llm_error_message")
    if "llm_fallback_used" in cols:
        op.drop_column("intakes", "llm_fallback_used")
