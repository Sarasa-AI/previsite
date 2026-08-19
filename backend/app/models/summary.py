from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base

class Summary(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)

    chief_complaint = Column(Text, nullable=True)
    history_present_illness = Column(Text, nullable=True)
    past_medical_history = Column(Text, nullable=True)
    medications = Column(Text, nullable=True)
    allergies = Column(Text, nullable=True)
    assessment = Column(Text, nullable=True)
    is_hpi_complete = Column(Boolean, default=False)
    soap_note = Column(Text, nullable=True)
    soap_citations_json = Column(Text, nullable=True)
    soap_verification_status = Column(Text, nullable=True)
    # Structured, PMH-validated discrepancies produced by the SOAP conflict stage.
    # Persisted so the Doctor Workspace can surface conflicts as first-class
    # signals instead of only as prose appended to the SOAP markdown.
    soap_conflicts_json = Column(Text, nullable=True)
    legacy_soap_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Session", back_populates="summary")
