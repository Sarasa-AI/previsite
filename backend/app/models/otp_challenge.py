"""OTP challenge rows — code hash only; never store plaintext OTP."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.database import Base


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"

    id = Column(String(36), primary_key=True)
    phone = Column(String(16), nullable=False, index=True)
    code_hash = Column(String(64), nullable=False)
    purpose = Column(String(32), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    request_ip = Column(String(64), nullable=True)
