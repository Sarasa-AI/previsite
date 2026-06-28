"""repair missing user profile columns

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-06-28
"""

from typing import Sequence, Union

from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS national_id VARCHAR(10)")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS age INTEGER")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS sex VARCHAR")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS weight DOUBLE PRECISION")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS height DOUBLE PRECISION")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_national_id ON users (national_id)"
    )

    op.execute(
        """
        DO $$ BEGIN
            ALTER TABLE sessions
            ADD COLUMN soap_status soapstatus NOT NULL DEFAULT 'PENDING';
        EXCEPTION
            WHEN duplicate_column THEN NULL;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE sessions ADD COLUMN IF NOT EXISTS soap_error_detail TEXT"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS soap_error_detail")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS soap_status")

    op.execute("DROP INDEX IF EXISTS ix_users_national_id")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS height")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS weight")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS sex")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS age")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS last_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS first_name")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS national_id")
