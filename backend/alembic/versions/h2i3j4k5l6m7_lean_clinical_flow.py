"""lean clinical flow: legacy_soap, condition_id, overview_json

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "h2i3j4k5l6m7"
down_revision: Union[str, None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("summaries", sa.Column("legacy_soap_json", sa.Text(), nullable=True))
    op.add_column("files", sa.Column("condition_id", sa.String(length=36), nullable=True))
    op.create_index("ix_files_condition_id", "files", ["condition_id"], unique=False)
    op.add_column(
        "patient_pmh",
        sa.Column("overview_json", JSONB(), nullable=True),
    )

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            """
            SELECT id, soap_note, soap_citations_json, soap_verification_status
            FROM summaries
            WHERE soap_note IS NOT NULL
            """
        )
    ).fetchall()

    for row in rows:
        import json
        from datetime import datetime, timezone

        payload = {
            "soap_note": row.soap_note,
            "soap_citations": json.loads(row.soap_citations_json)
            if row.soap_citations_json
            else [],
            "soap_verification_status": row.soap_verification_status,
            "archived_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            sa.text("UPDATE summaries SET legacy_soap_json = :payload WHERE id = :id"),
            {"payload": json.dumps(payload, ensure_ascii=False), "id": row.id},
        )


def downgrade() -> None:
    op.drop_column("patient_pmh", "overview_json")
    op.drop_index("ix_files_condition_id", table_name="files")
    op.drop_column("files", "condition_id")
    op.drop_column("summaries", "legacy_soap_json")
