"""Doctor verification lifecycle (admin-operated)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import DoctorVerificationStatus, User, UserRole
from app.services import refresh_token_service
from app.services.platform_identity_service import (
    ensure_doctor_profile,
    ensure_staff_membership,
    sync_doctor_profile_from_user,
)


def is_verified_doctor(user: User) -> bool:
    if user.role != UserRole.DOCTOR:
        return False
    status = user.verification_status
    if status is None:
        return False
    value = status.value if hasattr(status, "value") else str(status)
    return value == DoctorVerificationStatus.VERIFIED.value


async def list_doctors(db: AsyncSession) -> list[User]:
    result = await db.execute(
        select(User)
        .where(User.role == UserRole.DOCTOR)
        .order_by(User.id.asc())
    )
    return list(result.scalars().all())


async def get_doctor(db: AsyncSession, doctor_id: int) -> User | None:
    result = await db.execute(
        select(User).where(User.id == doctor_id, User.role == UserRole.DOCTOR)
    )
    return result.scalar_one_or_none()


async def verify_doctor(
    db: AsyncSession,
    *,
    doctor: User,
    admin: User,
) -> User:
    doctor.verification_status = DoctorVerificationStatus.VERIFIED
    doctor.verified_by = admin.id
    doctor.verified_at = datetime.now(timezone.utc)
    await sync_doctor_profile_from_user(db, doctor)
    await ensure_staff_membership(db, doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def suspend_doctor(db: AsyncSession, *, doctor: User) -> User:
    doctor.verification_status = DoctorVerificationStatus.SUSPENDED
    await sync_doctor_profile_from_user(db, doctor)
    await db.commit()
    await refresh_token_service.revoke_all_for_user(db, user_id=doctor.id)
    await db.refresh(doctor)
    return doctor


async def reinstate_doctor(
    db: AsyncSession,
    *,
    doctor: User,
    admin: User,
) -> User:
    doctor.verification_status = DoctorVerificationStatus.VERIFIED
    doctor.verified_by = admin.id
    doctor.verified_at = datetime.now(timezone.utc)
    await sync_doctor_profile_from_user(db, doctor)
    await ensure_staff_membership(db, doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def ensure_doctor_identity_rows(db: AsyncSession, doctor: User) -> None:
    """Create/sync DoctorProfile + default-org membership (no commit)."""
    await ensure_doctor_profile(db, doctor)
    await ensure_staff_membership(db, doctor)


async def reset_user_mfa(db: AsyncSession, *, user: User) -> None:
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_backup_codes_hash = None
    await db.commit()
    await refresh_token_service.revoke_all_for_user(db, user_id=user.id)


async def regenerate_backup_codes(db: AsyncSession, *, user: User) -> list[str]:
    from app.services import mfa_service

    if not user.mfa_enabled or not user.mfa_secret:
        raise ValueError("MFA is not enabled for this user")
    codes = mfa_service.generate_backup_codes()
    user.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(codes)
    await db.commit()
    return codes
