"""add privacy export_jobs and deletion_requests tables

Revision ID: u5d6e7f8g9h0
Revises: t4c5d6e7f8g9
Create Date: 2026-10-02
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u5d6e7f8g9h0"
down_revision: Union[str, None] = "t4c5d6e7f8g9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "privacy_export_jobs" not in tables:
        op.create_table(
            "privacy_export_jobs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("public_id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("storage_key", sa.String(length=512), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("download_expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_privacy_export_jobs_public_id"),
            "privacy_export_jobs",
            ["public_id"],
            unique=True,
        )
        op.create_index(
            op.f("ix_privacy_export_jobs_user_id"),
            "privacy_export_jobs",
            ["user_id"],
            unique=False,
        )

    if "account_deletion_requests" not in tables:
        op.create_table(
            "account_deletion_requests",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column(
                "requested_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("cool_off_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by_user_id", sa.Integer(), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
            sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_account_deletion_requests_user_id"),
            "account_deletion_requests",
            ["user_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_account_deletion_requests_status"),
            "account_deletion_requests",
            ["status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "account_deletion_requests" in tables:
        op.drop_index(
            op.f("ix_account_deletion_requests_status"),
            table_name="account_deletion_requests",
        )
        op.drop_index(
            op.f("ix_account_deletion_requests_user_id"),
            table_name="account_deletion_requests",
        )
        op.drop_table("account_deletion_requests")

    if "privacy_export_jobs" in tables:
        op.drop_index(
            op.f("ix_privacy_export_jobs_user_id"),
            table_name="privacy_export_jobs",
        )
        op.drop_index(
            op.f("ix_privacy_export_jobs_public_id"),
            table_name="privacy_export_jobs",
        )
        op.drop_table("privacy_export_jobs")
