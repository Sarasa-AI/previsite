"""SQLAlchemy ORM models for Workspace workflow persistence."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class WorkflowEventRecord(Base):
    """Append-only Workflow Event Store row (canonical workflow persistence)."""

    __tablename__ = "workflow_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)
    object_id = Column(String(64), nullable=True)
    context_hash = Column(String(64), nullable=True, index=True)
    payload = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
