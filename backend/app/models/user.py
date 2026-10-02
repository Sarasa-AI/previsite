from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from app.db.database import Base
import enum

class UserRole(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class DoctorVerificationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    SUSPENDED = "suspended"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # Nullable for OTP-only patients (no password).
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    # Unique only when present (partial unique index in Alembic).
    national_id = Column(String(10), index=True, nullable=True)
    # Canonical E.164 Iranian mobile; unique when present.
    phone = Column(String(16), index=True, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    sex = Column(String, nullable=True)
    weight = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PATIENT)
    is_active = Column(Boolean, nullable=False, default=True)
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, nullable=False, default=False)
    mfa_backup_codes_hash = Column(Text, nullable=True)
    medical_council_license = Column(String(64), nullable=True)
    specialty = Column(String(128), nullable=True)
    verification_status = Column(
        Enum(DoctorVerificationStatus, native_enum=False, length=32),
        nullable=True,
    )
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
