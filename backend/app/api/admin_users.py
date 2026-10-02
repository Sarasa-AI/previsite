"""Admin MFA management for admin accounts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_admin
from app.db.database import get_db
from app.models.user import User, UserRole
from app.schemas.doctor_admin import MfaRegenerateResponse
from app.services import doctor_lifecycle_service
from app.services.audit_service import (
    AUDIT_MFA_BACKUP_CODES_REGENERATED,
    AUDIT_MFA_RESET_BY_ADMIN,
    client_ip_from_request,
    record_audit,
)

router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


async def _admin_target(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")
    return user


@router.post("/{user_id}/mfa/reset")
async def reset_admin_mfa(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> dict:
    user = await _admin_target(db, user_id)
    had_mfa = bool(user.mfa_enabled)
    await doctor_lifecycle_service.reset_user_mfa(db, user=user)
    await record_audit(
        db,
        action=AUDIT_MFA_RESET_BY_ADMIN,
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip_from_request(request),
        previous_value=f"mfa_enabled={had_mfa}",
    )
    return {"status": "ok"}


@router.post("/{user_id}/mfa/regenerate-backup-codes", response_model=MfaRegenerateResponse)
async def regenerate_admin_backup_codes(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> MfaRegenerateResponse:
    user = await _admin_target(db, user_id)
    try:
        codes = await doctor_lifecycle_service.regenerate_backup_codes(db, user=user)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    await record_audit(
        db,
        action=AUDIT_MFA_BACKUP_CODES_REGENERATED,
        user_id=admin.id,
        resource_type="user",
        resource_id=user.id,
        ip_address=client_ip_from_request(request),
    )
    return MfaRegenerateResponse(backup_codes=codes)
