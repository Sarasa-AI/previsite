"""add patient profile fields and soap status

Revision ID: a1b2c3d4e5f6
Revises: 5260ac1c03a9
Create Date: 2026-06-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "5260ac1c03a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

soap_status_enum = sa.Enum(
    "pending", "generating", "failed", "ready", name="soapstatus"
)


def upgrade() -> None:
    bind = op.get_bind()
    soap_status_enum.create(bind, checkfirst=True)

    op.add_column("users", sa.Column("national_id", sa.String(length=10), nullable=True))
    op.add_column("users", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("age", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("sex", sa.String(), nullable=True))
    op.add_column("users", sa.Column("weight", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("height", sa.Float(), nullable=True))
    op.create_index(op.f("ix_users_national_id"), "users", ["national_id"], unique=True)

    op.add_column(
        "sessions",
        sa.Column(
            "soap_status",
            soap_status_enum,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column("sessions", sa.Column("soap_error_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "soap_error_detail")
    op.drop_column("sessions", "soap_status")
    soap_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index(op.f("ix_users_national_id"), table_name="users")
    op.drop_column("users", "height")
    op.drop_column("users", "weight")
    op.drop_column("users", "sex")
    op.drop_column("users", "age")
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
    op.drop_column("users", "national_id")
