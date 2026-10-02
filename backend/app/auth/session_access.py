"""Resource-level session access for patients and doctors."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Session as SessionModel
from app.models import User
from app.models.user import UserRole
from app.services.doctor_lifecycle_service import is_verified_doctor


def _role_value(user: User) -> str:
    role = user.role
    return role.value if hasattr(role, "value") else str(role)


def is_doctor(user: User) -> bool:
    return _role_value(user) == UserRole.DOCTOR.value


def is_patient(user: User) -> bool:
    return _role_value(user) == UserRole.PATIENT.value


def is_admin(user: User) -> bool:
    return _role_value(user) == UserRole.ADMIN.value


def doctor_may_access_session(session: SessionModel, user: User) -> bool:
    """Return True if a doctor may view/mutate this session under current mode."""
    if is_doctor(user) and not is_verified_doctor(user):
        return False
    if settings.single_doctor_mode:
        return True
    if session.doctor_id is None:
        return True  # unassigned / pending queue
    return session.doctor_id == user.id


async def claim_session_if_unassigned(
    db: AsyncSession, session: SessionModel, user: User
) -> SessionModel:
    """Atomically assign doctor_id on first doctor open when unassigned.

    Uses a single conditional UPDATE so two concurrent doctors cannot both claim.
    The loser sees the same denial as for a session already owned by someone else.
    SINGLE_DOCTOR_MODE remains a no-claim bypass.
    Admins follow the same claim path as doctors for clinical access.
    """
    if not (is_doctor(user) or is_admin(user)):
        return session
    if is_doctor(user) and not is_verified_doctor(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Doctor account is not verified",
        )
    if settings.single_doctor_mode:
        return session
    if session.doctor_id is not None:
        return session

    result = await db.execute(
        update(SessionModel)
        .where(SessionModel.id == session.id)
        .where(SessionModel.doctor_id.is_(None))
        .values(doctor_id=user.id)
    )
    await db.commit()

    if result.rowcount and result.rowcount > 0:
        await db.refresh(session)
        return session

    # Lost the race — reload and re-check ownership.
    await db.refresh(session)
    if session.doctor_id == user.id:
        return session
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this session",
    )


async def get_authorized_session(
    db: AsyncSession,
    session_id: int,
    current_user: User,
    *,
    claim: bool = True,
    not_found_as_403: bool = True,
    ip_address: str | None = None,
    record_denial: bool = True,
) -> SessionModel:
    """Load a session and enforce patient ownership / doctor RBAC.

    Patients: only their own sessions.
    Doctors: own assigned sessions, or unassigned (pending); claim-on-open when claim=True.
    Admins: same as doctors for clinical access (no blanket bypass unless single_doctor_mode).
    """
    result = await db.execute(
        select(SessionModel).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()

    denied = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied to this session",
    )
    missing = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Session not found",
    )

    async def _deny(exc: HTTPException) -> None:
        if record_denial and current_user is not None:
            try:
                from app.services.audit_service import (
                    AUDIT_SESSION_ACCESS_DENIED,
                    record_audit,
                )

                await record_audit(
                    db,
                    action=AUDIT_SESSION_ACCESS_DENIED,
                    user_id=current_user.id,
                    resource_type="session",
                    resource_id=session_id,
                    ip_address=ip_address,
                )
            except Exception:
                pass
        raise exc

    if not session:
        await _deny(denied if not_found_as_403 else missing)

    if is_patient(current_user):
        if session.patient_id != current_user.id:
            await _deny(denied)
        return session

    if is_doctor(current_user) or is_admin(current_user):
        if is_doctor(current_user) and not is_verified_doctor(current_user):
            await _deny(
                HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Doctor account is not verified",
                )
            )
        if not doctor_may_access_session(session, current_user):
            await _deny(denied)
        if claim:
            try:
                session = await claim_session_if_unassigned(db, session, current_user)
            except HTTPException as exc:
                await _deny(exc)
        return session

    await _deny(denied)


def doctor_session_list_filter(query, current_user: User):
    """Restrict doctor session list to assigned + unassigned unless single-doctor mode."""
    if is_doctor(current_user) and not is_verified_doctor(current_user):
        return query.where(SessionModel.id < 0)
    if settings.single_doctor_mode:
        return query
    return query.where(
        or_(
            SessionModel.doctor_id.is_(None),
            SessionModel.doctor_id == current_user.id,
        )
    )


async def doctor_may_access_patient(
    db: AsyncSession, patient_id: int, current_user: User
) -> bool:
    """True if doctor may read patient-level data (e.g. PMH overview)."""
    if is_doctor(current_user) and not is_verified_doctor(current_user):
        return False
    if settings.single_doctor_mode:
        return True
    result = await db.execute(
        select(SessionModel.id)
        .where(SessionModel.patient_id == patient_id)
        .where(
            or_(
                SessionModel.doctor_id.is_(None),
                SessionModel.doctor_id == current_user.id,
            )
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
