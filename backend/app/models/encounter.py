"""Encounter — central clinical visit entity (org-scoped)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.db.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class EncounterStatus(str, enum.Enum):
    DRAFT = "draft"
    INTAKE = "intake"
    AWAITING_CLINICIAN = "awaiting_clinician"
    ACCEPTED = "accepted"
    IN_CONSULTATION = "in_consultation"
    SIGNED = "signed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class Encounter(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "encounters"
    __table_args__ = (
        CheckConstraint(
            "(subject_user_id IS NOT NULL AND subject_family_member_id IS NULL) "
            "OR (subject_user_id IS NULL AND subject_family_member_id IS NOT NULL)",
            name="ck_encounters_subject_xor",
        ),
        CheckConstraint(
            "status <> 'signed' OR (signed_at IS NOT NULL AND signed_by_user_id IS NOT NULL)",
            name="ck_encounters_signed_requires_signer",
        ),
        CheckConstraint(
            "status <> 'accepted' OR (accepted_at IS NOT NULL AND accepted_by_user_id IS NOT NULL)",
            name="ck_encounters_accepted_requires_acceptor",
        ),
        Index("ix_encounters_org_status", "organization_id", "status"),
        Index("ix_encounters_subject_user", "subject_user_id"),
        Index("ix_encounters_subject_family_member", "subject_family_member_id"),
        Index("ix_encounters_doctor_user", "doctor_user_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    subject_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    subject_family_member_id = Column(
        Uuid(as_uuid=True), ForeignKey("family_members.id"), nullable=True
    )
    initiated_by_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    doctor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    consent_user_id = Column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    consent_snapshot = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    status = Column(
        Enum(
            EncounterStatus,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
    )
    chief_complaint = Column(Text, nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    signed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    organization = relationship("Organization", foreign_keys=[organization_id])
    subject_user = relationship("User", foreign_keys=[subject_user_id])
    subject_family_member = relationship(
        "FamilyMember", foreign_keys=[subject_family_member_id]
    )
    initiated_by = relationship("User", foreign_keys=[initiated_by_user_id])
    doctor = relationship("User", foreign_keys=[doctor_user_id])
    consent_user = relationship("User", foreign_keys=[consent_user_id])
