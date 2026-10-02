"""Admin-only doctor lifecycle and privileged-user MFA management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_active_admin
from app.db.database import get_db
from app.models.user import DoctorVerificationStatus, User, UserRole
from app.schemas.doctor_admin import DoctorAdminItem, MfaRegenerateResponse
from app.services import doctor_lifecycle_service
from app.services.audit_service import (
    AUDIT_DOCTOR_REINSTATED,
    AUDIT_DOCTOR_SUSPENDED,
    AUDIT_DOCTOR_VERIFIED,
    AUDIT_MFA_BACKUP_CODES_REGENERATED,
    AUDIT_MFA_RESET_BY_ADMIN,
    client_ip_from_request,
    record_audit,
)

router = APIRouter(prefix="/api/admin/doctors", tags=["admin-doctors"])


def _doctor_item(user: User) -> DoctorAdminItem:
    return DoctorAdminItem.model_validate(user)


@router.get("", response_model=list[DoctorAdminItem])
async def list_doctors(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_admin),
) -> list[DoctorAdminItem]:
    doctors = await doctor_lifecycle_service.list_doctors(db)
    return [_doctor_item(d) for d in doctors]


@router.post("/{doctor_id}/verify", response_model=DoctorAdminItem)
async def verify_doctor(
    doctor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> DoctorAdminItem:
    doctor = await doctor_lifecycle_service.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if doctor.verification_status == DoctorVerificationStatus.VERIFIED:
        return _doctor_item(doctor)

    doctor = await doctor_lifecycle_service.verify_doctor(db, doctor=doctor, admin=admin)
    await record_audit(
        db,
        action=AUDIT_DOCTOR_VERIFIED,
        user_id=admin.id,
        resource_type="user",
        resource_id=doctor.id,
        ip_address=client_ip_from_request(request),
        previous_value=f"status={DoctorVerificationStatus.PENDING.value}",
    )
    return _doctor_item(doctor)


@router.post("/{doctor_id}/suspend", response_model=DoctorAdminItem)
async def suspend_doctor(
    doctor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> DoctorAdminItem:
    doctor = await doctor_lifecycle_service.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if doctor.verification_status == DoctorVerificationStatus.SUSPENDED:
        return _doctor_item(doctor)

    previous = doctor.verification_status.value if doctor.verification_status else None
    doctor = await doctor_lifecycle_service.suspend_doctor(db, doctor=doctor)
    await record_audit(
        db,
        action=AUDIT_DOCTOR_SUSPENDED,
        user_id=admin.id,
        resource_type="user",
        resource_id=doctor.id,
        ip_address=client_ip_from_request(request),
        previous_value=f"status={previous}",
    )
    return _doctor_item(doctor)


@router.post("/{doctor_id}/reinstate", response_model=DoctorAdminItem)
async def reinstate_doctor(
    doctor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> DoctorAdminItem:
    doctor = await doctor_lifecycle_service.get_doctor(db, doctor_id)
    if not doctor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")
    if doctor.verification_status == DoctorVerificationStatus.VERIFIED:
        return _doctor_item(doctor)

    previous = doctor.verification_status.value if doctor.verification_status else None
    doctor = await doctor_lifecycle_service.reinstate_doctor(db, doctor=doctor, admin=admin)
    await record_audit(
        db,
        action=AUDIT_DOCTOR_REINSTATED,
        user_id=admin.id,
        resource_type="user",
        resource_id=doctor.id,
        ip_address=client_ip_from_request(request),
        previous_value=f"status={previous}",
    )
    return _doctor_item(doctor)


async def _privileged_user_for_mfa(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or user.role not in (UserRole.DOCTOR, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Privileged user not found",
        )
    return user


@router.post("/{doctor_id}/mfa/reset")
async def reset_doctor_mfa(
    doctor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> dict:
    user = await _privileged_user_for_mfa(db, doctor_id)
    if user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

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


@router.post("/{doctor_id}/mfa/regenerate-backup-codes", response_model=MfaRegenerateResponse)
async def regenerate_doctor_backup_codes(
    doctor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_active_admin),
) -> MfaRegenerateResponse:
    user = await _privileged_user_for_mfa(db, doctor_id)
    if user.role != UserRole.DOCTOR:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Doctor not found")

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
