"""add soap_conflicts_json to summaries

Persists the structured, PMH-validated discrepancies produced by the SOAP
conflict stage. Before this, conflicts existed only as prose appended to the SOAP
markdown and a count in telemetry, so the Doctor Workspace had no structured
source for its CONFLICTS object and always rendered it hidden.

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-08-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o9p0q1r2s3t4"
down_revision: Union[str, None] = "n8o9p0q1r2s3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column("soap_conflicts_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("summaries", "soap_conflicts_json")
