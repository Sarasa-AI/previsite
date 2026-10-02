"""add doctor verification and license fields

Revision ID: v6e7f8g9h0i1
Revises: u5d6e7f8g9h0
Create Date: 2026-10-02
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "v6e7f8g9h0i1"
down_revision: Union[str, None] = "u5d6e7f8g9h0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in sa.inspect(bind).get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    if "users" not in sa.inspect(bind).get_table_names():
        return

    existing = _column_names("users")

    if "medical_council_license" not in existing:
        op.add_column(
            "users",
            sa.Column("medical_council_license", sa.String(length=64), nullable=True),
        )
    if "specialty" not in existing:
        op.add_column(
            "users",
            sa.Column("specialty", sa.String(length=128), nullable=True),
        )
    if "verification_status" not in existing:
        op.add_column(
            "users",
            sa.Column("verification_status", sa.String(length=32), nullable=True),
        )
    if "verified_by" not in existing:
        op.add_column(
            "users",
            sa.Column("verified_by", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_users_verified_by_users",
            "users",
            "users",
            ["verified_by"],
            ["id"],
        )
    if "verified_at" not in existing:
        op.add_column(
            "users",
            sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        )

    username = (os.environ.get("SEED_DOCTOR_USERNAME") or "bagherzade").strip()
    if not username:
        username = "bagherzade"
    seed_email = f"{username}@doctor.com"
    now = datetime.now(timezone.utc)
    # role enum values differ by dialect (Postgres: DOCTOR; SQLite/string: doctor).
    op.execute(
        sa.text(
            """
            UPDATE users
            SET verification_status = 'verified',
                verified_at = COALESCE(verified_at, :verified_at)
            WHERE lower(email) = lower(:email)
              AND lower(CAST(role AS VARCHAR)) = 'doctor'
              AND (verification_status IS NULL OR verification_status = 'pending')
            """
        ).bindparams(email=seed_email, verified_at=now)
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "users" not in sa.inspect(bind).get_table_names():
        return
    existing = _column_names("users")
    if "verified_at" in existing:
        op.drop_column("users", "verified_at")
    if "verified_by" in existing:
        try:
            op.drop_constraint("fk_users_verified_by_users", "users", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("users", "verified_by")
    if "verification_status" in existing:
        op.drop_column("users", "verification_status")
    if "specialty" in existing:
        op.drop_column("users", "specialty")
    if "medical_council_license" in existing:
        op.drop_column("users", "medical_council_license")
