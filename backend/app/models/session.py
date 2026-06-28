from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
import enum

class SessionStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SoapStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    FAILED = "failed"
    READY = "ready"


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(SessionStatus), default=SessionStatus.ACTIVE)
    soap_status = Column(Enum(SoapStatus), default=SoapStatus.PENDING, nullable=False)
    soap_error_detail = Column(Text, nullable=True)
    initial_complaint = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")
    files = relationship("File", back_populates="session", cascade="all, delete-orphan")
    summary = relationship("Summary", back_populates="session", uselist=False, cascade="all, delete-orphan")
    intake = relationship("Intake", back_populates="session", uselist=False, cascade="all, delete-orphan")
