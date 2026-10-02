"""add workflow_events table

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-08-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m7n8o9p0q1r2"
down_revision: Union[str, None] = "l6m7n8o9p0q1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("object_id", sa.String(length=64), nullable=True),
        sa.Column("context_hash", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_events_id", "workflow_events", ["id"], unique=False)
    op.create_index(
        "ix_workflow_events_session_id", "workflow_events", ["session_id"], unique=False
    )
    op.create_index(
        "ix_workflow_events_actor_user_id",
        "workflow_events",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_events_event_type", "workflow_events", ["event_type"], unique=False
    )
    op.create_index(
        "ix_workflow_events_context_hash",
        "workflow_events",
        ["context_hash"],
        unique=False,
    )
    op.create_index(
        "ix_workflow_events_created_at", "workflow_events", ["created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_events_created_at", table_name="workflow_events")
    op.drop_index("ix_workflow_events_context_hash", table_name="workflow_events")
    op.drop_index("ix_workflow_events_event_type", table_name="workflow_events")
    op.drop_index("ix_workflow_events_actor_user_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_session_id", table_name="workflow_events")
    op.drop_index("ix_workflow_events_id", table_name="workflow_events")
    op.drop_table("workflow_events")
