"""add mfa_setup_challenges table

Revision ID: r2a3b4c5d6e7
Revises: q1r2s3t4u5v6
Create Date: 2026-10-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "r2a3b4c5d6e7"
down_revision: Union[str, None] = "q1r2s3t4u5v6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "mfa_setup_challenges" in tables:
        return

    op.create_table(
        "mfa_setup_challenges",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mfa_setup_challenges_user_id"),
        "mfa_setup_challenges",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mfa_setup_challenges_expires_at"),
        "mfa_setup_challenges",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "mfa_setup_challenges" not in tables:
        return
    op.drop_index(
        op.f("ix_mfa_setup_challenges_expires_at"),
        table_name="mfa_setup_challenges",
    )
    op.drop_index(
        op.f("ix_mfa_setup_challenges_user_id"),
        table_name="mfa_setup_challenges",
    )
    op.drop_table("mfa_setup_challenges")
