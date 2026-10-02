"""Metadata-only log of external LLM/embedding egress (no prompt/response content)."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class LlmEgressLog(Base):
    __tablename__ = "llm_egress_log"
    __table_args__ = (
        Index("ix_llm_egress_log_session_timestamp", "session_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    session_id = Column(Integer, nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    provider = Column(String(64), nullable=False)
    purpose = Column(String(64), nullable=False)
    scrubber_version = Column(String(16), nullable=False)
    # JSON object: category -> replacement count. Never store content.
    replacement_counts = Column(Text, nullable=False, default="{}")
    # JSON array of field category labels included in the outbound call.
    field_categories = Column(Text, nullable=False, default="[]")
    response_status = Column(String(32), nullable=False)
    latency_ms = Column(Float, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
