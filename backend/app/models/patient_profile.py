"""Patient clinical demographics (1:1 with User). Auth fields stay on users."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.db.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class PatientProfile(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "patient_profiles"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    date_of_birth = Column(Date, nullable=True)
    age_years = Column(Integer, nullable=True)
    sex = Column(String(32), nullable=True)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
