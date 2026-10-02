"""Doctor professional profile (1:1 with User). Dual-written with users.* for now."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.db.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin
from app.models.user import DoctorVerificationStatus


class DoctorProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "doctor_profiles"
    __table_args__ = (
        Index(
            "uq_doctor_profiles_council_live",
            "medical_council_number",
            unique=True,
            sqlite_where=text(
                "medical_council_number IS NOT NULL AND deleted_at IS NULL"
            ),
            postgresql_where=text(
                "medical_council_number IS NOT NULL AND deleted_at IS NULL"
            ),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    medical_council_number = Column(String(64), nullable=True)
    specialty = Column(String(128), nullable=True)
    verification_status = Column(
        Enum(
            DoctorVerificationStatus,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=DoctorVerificationStatus.PENDING,
    )
    verified_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    verified_by = relationship("User", foreign_keys=[verified_by_user_id])
