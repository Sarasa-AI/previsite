"""add patient_consents table

Revision ID: t4c5d6e7f8g9
Revises: s3b4c5d6e7f8
Create Date: 2026-10-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t4c5d6e7f8g9"
down_revision: Union[str, None] = "s3b4c5d6e7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "patient_consents" in tables:
        return

    op.create_table(
        "patient_consents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("consent_key", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
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
        op.f("ix_patient_consents_user_id"),
        "patient_consents",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_patient_consents_consent_key"),
        "patient_consents",
        ["consent_key"],
        unique=False,
    )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "patient_consents" not in tables:
        return
    op.drop_index(op.f("ix_patient_consents_consent_key"), table_name="patient_consents")
    op.drop_index(op.f("ix_patient_consents_user_id"), table_name="patient_consents")
    op.drop_table("patient_consents")
