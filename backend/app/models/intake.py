from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class Intake(Base):
    __tablename__ = "intakes"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, unique=True)

    current_layer = Column(Integer, default=1, nullable=False)
    demographics_json = Column(Text, nullable=True)
    hpi_questions_json = Column(Text, nullable=True)
    hpi_answers_json = Column(Text, nullable=True)
    question_strategy = Column(Text, nullable=True)
    clinical_summary_json = Column(Text, nullable=True)
    medical_history_json = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    session = relationship("Session", back_populates="intake")
