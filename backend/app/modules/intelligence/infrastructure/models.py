"""SQLAlchemy ORM models for Clinical Intelligence persistence."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class ClinicalFindingRecord(Base):
    """Persisted ClinicalFinding row."""

    __tablename__ = "clinical_findings"

    id = Column(Integer, primary_key=True, index=True)
    finding_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    category = Column(String(64), nullable=False, index=True)
    severity = Column(String(32), nullable=False)
    title = Column(String(512), nullable=False)
    summary = Column(Text, nullable=False, default="")
    confidence = Column(Float, nullable=True)  # None => unknown
    evidence_json = Column(Text, nullable=True)
    source = Column(String(64), nullable=False)
    source_id = Column(String(128), nullable=True)
    context_hash = Column(String(64), nullable=True)
    schema_version = Column(String(32), nullable=False, default="1.0.0")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class RiskSignalRecord(Base):
    """Persisted RiskSignal row."""

    __tablename__ = "risk_signals"

    id = Column(Integer, primary_key=True, index=True)
    risk_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    risk_key = Column(String(128), nullable=False, index=True)
    level = Column(String(32), nullable=False)
    title = Column(String(512), nullable=False)
    finding_id = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    evidence_json = Column(Text, nullable=True)
    schema_version = Column(String(32), nullable=False, default="1.0.0")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )


class RecommendationRecord(Base):
    """Persisted Recommendation row."""

    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    recommendation_id = Column(String(64), nullable=False, unique=True, index=True)
    session_id = Column(
        Integer,
        ForeignKey("sessions.id"),
        nullable=False,
        index=True,
    )
    kind = Column(String(64), nullable=False)
    title = Column(String(512), nullable=False)
    rationale = Column(Text, nullable=False, default="")
    status = Column(String(32), nullable=False, default="active", index=True)
    finding_id = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=True)
    evidence_json = Column(Text, nullable=True)
    schema_version = Column(String(32), nullable=False, default="1.0.0")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
