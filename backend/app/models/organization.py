"""Organization (clinic / tenant) and staff membership."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.db.database import Base
from app.models.mixins import SoftDeleteMixin, TimestampMixin

# Stable default tenant — duplicated as a literal in the Alembic revision.
DEFAULT_ORGANIZATION_ID = uuid.UUID("5c0a1d7e-4b3f-5a61-9c2e-1f0a6d8b7e41")
DEFAULT_ORGANIZATION_SLUG = "previsit"
DEFAULT_ORGANIZATION_NAME = "PreVisit"


class MembershipRole(str, enum.Enum):
    DOCTOR = "doctor"
    ADMIN = "admin"


class MembershipStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Organization(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"
    __table_args__ = (
        Index(
            "uq_organizations_slug_live",
            "slug",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    slug = Column(String(64), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)

    memberships = relationship("OrganizationMembership", back_populates="organization")


class OrganizationMembership(Base, TimestampMixin):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_org_user",
        ),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(
        Uuid(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(
        Enum(
            MembershipRole,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
    )
    status = Column(
        Enum(
            MembershipStatus,
            native_enum=False,
            length=32,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
        ),
        nullable=False,
        default=MembershipStatus.ACTIVE,
    )

    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", foreign_keys=[user_id])
