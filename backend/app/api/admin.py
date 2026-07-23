from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_admin
from app.db.database import get_db
from app.models import User
from app.models.audit_log import AuditLog
from app.services.drug_matcher import drug_matcher

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AuditLogItem(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    timestamp: Optional[str] = None
    ip_address: Optional[str] = None
    previous_value: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


@router.post("/refresh-drug-cache")
async def refresh_drug_cache(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
) -> dict:
    await drug_matcher.refresh_cache(db)
    return {"status": "ok", "entry_count": len(drug_matcher._entries)}


@router.get("/audit-logs", response_model=list[AuditLogItem])
async def list_audit_logs(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditLogItem]:
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        AuditLogItem(
            id=row.id,
            user_id=row.user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            timestamp=row.timestamp.isoformat() if row.timestamp else None,
            ip_address=row.ip_address,
            previous_value=row.previous_value,
        )
        for row in rows
    ]
