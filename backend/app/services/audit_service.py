"""Best-effort audit logging helpers."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


async def record_audit(
    db: AsyncSession,
    *,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str | int] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Persist an audit row; never raise to the caller (fail-soft)."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            ip_address=ip_address,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        logger.exception("Failed to write audit log action=%s", action)
        try:
            await db.rollback()
        except Exception:
            logger.exception("Failed to rollback after audit log error")
