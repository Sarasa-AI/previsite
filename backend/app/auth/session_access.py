"""Resource-level session access for patients and doctors."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Session as SessionModel
from app.models import User
from app.models.user import UserRole


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
    if settings.single_doctor_mode:
        return True
    if session.doctor_id is None:
        return True  # unassigned / pending queue
    return session.doctor_id == user.id


async def claim_session_if_unassigned(
    db: AsyncSession, session: SessionModel, user: User
) -> SessionModel:
    """Assign doctor_id on first doctor open when unassigned and not single-doctor mode."""
    if not is_doctor(user):
        return session
    if settings.single_doctor_mode:
        return session
    if session.doctor_id is None:
        session.doctor_id = user.id
        await db.commit()
        await db.refresh(session)
    return session


async def get_authorized_session(
    db: AsyncSession,
    session_id: int,
    current_user: User,
    *,
    claim: bool = True,
    not_found_as_403: bool = True,
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

    if not session:
        raise denied if not_found_as_403 else missing

    if is_patient(current_user):
        if session.patient_id != current_user.id:
            raise denied
        return session

    if is_doctor(current_user) or is_admin(current_user):
        if not doctor_may_access_session(session, current_user):
            raise denied
        if claim:
            session = await claim_session_if_unassigned(db, session, current_user)
        return session

    raise denied


def doctor_session_list_filter(query, current_user: User):
    """Restrict doctor session list to assigned + unassigned unless single-doctor mode."""
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
