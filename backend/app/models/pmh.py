from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class PatientPMH(Base):
    """Patient-level medical history. answers_json is deprecated; use overview_json."""

    __tablename__ = "patient_pmh"

    patient_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    answers_json = Column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    overview_json = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    last_updated = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient = relationship("User", foreign_keys=[patient_id])
