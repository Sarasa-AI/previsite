"""Append-only audit trail for security-relevant events."""

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.db.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ip_address = Column(String(64), nullable=True)
    previous_value = Column(Text, nullable=True)
