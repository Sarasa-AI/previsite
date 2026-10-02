"""Patient-initiated account erasure requests (cool-off + admin approval + script)."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class DeletionRequestStatus:
    PENDING_COOL_OFF = "pending_cool_off"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AccountDeletionRequest(Base):
    __tablename__ = "account_deletion_requests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        String(32),
        nullable=False,
        default=DeletionRequestStatus.PENDING_COOL_OFF,
        index=True,
    )
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    cool_off_until = Column(DateTime(timezone=True), nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
