"""P2-B: phone OTP identity + LLM egress log

Revision ID: w7f8g9h0i1j2
Revises: v6e7f8g9h0i1
Create Date: 2026-10-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w7f8g9h0i1j2"
down_revision: Union[str, None] = "v6e7f8g9h0i1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def _index_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {idx["name"] for idx in sa.inspect(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    dialect = bind.dialect.name

    if "users" in tables:
        existing = _column_names("users")
        indexes = _index_names("users")

        if "phone" not in existing:
            op.add_column(
                "users",
                sa.Column("phone", sa.String(length=16), nullable=True),
            )

        # hashed_password → nullable for OTP-only patients
        if "hashed_password" in existing:
            if dialect == "postgresql":
                op.execute(
                    sa.text(
                        "ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"
                    )
                )
            # SQLite cannot easily alter nullability; create_all / recreate handles tests.

        # Partial unique indexes for phone and national_id (when present)
        if "uq_users_phone_not_null" not in indexes:
            if dialect == "postgresql":
                op.execute(
                    sa.text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_not_null "
                        "ON users (phone) WHERE phone IS NOT NULL"
                    )
                )
            else:
                # SQLite supports partial unique indexes.
                op.execute(
                    sa.text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_not_null "
                        "ON users (phone) WHERE phone IS NOT NULL"
                    )
                )

        if "uq_users_national_id_not_null" not in indexes:
            op.execute(
                sa.text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_national_id_not_null "
                    "ON users (national_id) WHERE national_id IS NOT NULL"
                )
            )

        # Non-unique lookup index on phone if missing
        if "ix_users_phone" not in indexes:
            op.create_index("ix_users_phone", "users", ["phone"], unique=False)

    if "otp_challenges" not in tables:
        op.create_table(
            "otp_challenges",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("phone", sa.String(length=16), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False),
            sa.Column("purpose", sa.String(length=32), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("request_ip", sa.String(length=64), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_otp_challenges_phone", "otp_challenges", ["phone"])
        op.create_index("ix_otp_challenges_purpose", "otp_challenges", ["purpose"])
        op.create_index("ix_otp_challenges_expires_at", "otp_challenges", ["expires_at"])

    tables = set(sa.inspect(bind).get_table_names())
    if "llm_egress_log" not in tables:
        op.create_table(
            "llm_egress_log",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(length=64), nullable=False),
            sa.Column("purpose", sa.String(length=64), nullable=False),
            sa.Column("scrubber_version", sa.String(length=16), nullable=False),
            sa.Column("replacement_counts", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("field_categories", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("response_status", sa.String(length=32), nullable=False),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("prompt_tokens", sa.Integer(), nullable=True),
            sa.Column("completion_tokens", sa.Integer(), nullable=True),
            sa.Column("total_tokens", sa.Integer(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_llm_egress_log_created_at", "llm_egress_log", ["created_at"])
        op.create_index("ix_llm_egress_log_session_id", "llm_egress_log", ["session_id"])
        op.create_index("ix_llm_egress_log_user_id", "llm_egress_log", ["user_id"])
        op.create_index(
            "ix_llm_egress_log_session_timestamp",
            "llm_egress_log",
            ["session_id", "created_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "llm_egress_log" in tables:
        op.drop_table("llm_egress_log")

    if "otp_challenges" in tables:
        op.drop_table("otp_challenges")

    if "users" in tables:
        indexes = _index_names("users")
        cols = _column_names("users")
        for name in (
            "ix_users_phone",
            "uq_users_phone_not_null",
            "uq_users_national_id_not_null",
        ):
            if name in indexes:
                op.drop_index(name, table_name="users")
        if "phone" in cols:
            op.drop_column("users", "phone")
