"""add clinical intelligence tables

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n8o9p0q1r2s3"
down_revision: Union[str, None] = "m7n8o9p0q1r2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "clinical_findings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("finding_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=True),
        sa.Column("context_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("finding_id"),
    )
    op.create_index("ix_clinical_findings_id", "clinical_findings", ["id"])
    op.create_index(
        "ix_clinical_findings_finding_id", "clinical_findings", ["finding_id"]
    )
    op.create_index(
        "ix_clinical_findings_session_id", "clinical_findings", ["session_id"]
    )
    op.create_index("ix_clinical_findings_category", "clinical_findings", ["category"])
    op.create_index(
        "ix_clinical_findings_created_at", "clinical_findings", ["created_at"]
    )

    op.create_table(
        "risk_signals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("risk_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("risk_key", sa.String(length=128), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("finding_id", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("risk_id"),
    )
    op.create_index("ix_risk_signals_id", "risk_signals", ["id"])
    op.create_index("ix_risk_signals_risk_id", "risk_signals", ["risk_id"])
    op.create_index("ix_risk_signals_session_id", "risk_signals", ["session_id"])
    op.create_index("ix_risk_signals_risk_key", "risk_signals", ["risk_key"])
    op.create_index("ix_risk_signals_created_at", "risk_signals", ["created_at"])

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recommendation_id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status", sa.String(length=32), nullable=False, server_default="active"
        ),
        sa.Column("finding_id", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column(
            "schema_version",
            sa.String(length=32),
            nullable=False,
            server_default="1.0.0",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recommendation_id"),
    )
    op.create_index("ix_recommendations_id", "recommendations", ["id"])
    op.create_index(
        "ix_recommendations_recommendation_id",
        "recommendations",
        ["recommendation_id"],
    )
    op.create_index("ix_recommendations_session_id", "recommendations", ["session_id"])
    op.create_index("ix_recommendations_status", "recommendations", ["status"])
    op.create_index("ix_recommendations_created_at", "recommendations", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_recommendations_created_at", table_name="recommendations")
    op.drop_index("ix_recommendations_status", table_name="recommendations")
    op.drop_index("ix_recommendations_session_id", table_name="recommendations")
    op.drop_index("ix_recommendations_recommendation_id", table_name="recommendations")
    op.drop_index("ix_recommendations_id", table_name="recommendations")
    op.drop_table("recommendations")

    op.drop_index("ix_risk_signals_created_at", table_name="risk_signals")
    op.drop_index("ix_risk_signals_risk_key", table_name="risk_signals")
    op.drop_index("ix_risk_signals_session_id", table_name="risk_signals")
    op.drop_index("ix_risk_signals_risk_id", table_name="risk_signals")
    op.drop_index("ix_risk_signals_id", table_name="risk_signals")
    op.drop_table("risk_signals")

    op.drop_index("ix_clinical_findings_created_at", table_name="clinical_findings")
    op.drop_index("ix_clinical_findings_category", table_name="clinical_findings")
    op.drop_index("ix_clinical_findings_session_id", table_name="clinical_findings")
    op.drop_index("ix_clinical_findings_finding_id", table_name="clinical_findings")
    op.drop_index("ix_clinical_findings_id", table_name="clinical_findings")
    op.drop_table("clinical_findings")
