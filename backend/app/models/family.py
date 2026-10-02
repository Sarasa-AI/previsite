"""Family group owned by an account-holder; members may be dependents without login."""

from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.db.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin


class FamilyGroup(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "family_groups"
    __table_args__ = (
        Index(
            "uq_family_groups_one_live_owner",
            "owner_user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    owner = relationship("User", foreign_keys=[owner_user_id])
    members = relationship("FamilyMember", back_populates="family_group")


class FamilyMember(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "family_members"
    __table_args__ = (
        Index(
            "uq_family_members_user_live",
            "user_id",
            unique=True,
            sqlite_where=text("user_id IS NOT NULL AND deleted_at IS NULL"),
            postgresql_where=text("user_id IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    family_group_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("family_groups.id"),
        nullable=False,
        index=True,
    )
    # Null means dependent without a login.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    display_name = Column(String(200), nullable=False)
    relationship_to_owner = Column(String(32), nullable=False)
    date_of_birth = Column(Date, nullable=True)
    sex = Column(String(32), nullable=True)

    family_group = relationship("FamilyGroup", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])
