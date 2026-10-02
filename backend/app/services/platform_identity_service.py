"""P3 helpers: patient/doctor profiles, default org membership, encounter create."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.doctor_profile import DoctorProfile
from app.models.encounter import Encounter, EncounterStatus
from app.models.organization import (
    DEFAULT_ORGANIZATION_ID,
    DEFAULT_ORGANIZATION_NAME,
    DEFAULT_ORGANIZATION_SLUG,
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationMembership,
)
from app.models.patient_profile import PatientProfile
from app.models.user import DoctorVerificationStatus, User, UserRole


async def ensure_default_organization(db: AsyncSession) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.id == DEFAULT_ORGANIZATION_ID)
    )
    org = result.scalar_one_or_none()
    if org is not None:
        return org
    by_slug = await db.execute(
        select(Organization).where(Organization.slug == DEFAULT_ORGANIZATION_SLUG)
    )
    org = by_slug.scalar_one_or_none()
    if org is not None:
        return org
    org = Organization(
        id=DEFAULT_ORGANIZATION_ID,
        name=DEFAULT_ORGANIZATION_NAME,
        slug=DEFAULT_ORGANIZATION_SLUG,
        is_default=True,
    )
    db.add(org)
    await db.flush()
    return org


def build_patient_profile_for_user(user: User) -> PatientProfile:
    return PatientProfile(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        age_years=user.age,
        sex=user.sex,
        weight_kg=user.weight,
        height_cm=user.height,
    )


async def ensure_patient_profile(db: AsyncSession, user: User) -> PatientProfile:
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    profile = build_patient_profile_for_user(user)
    db.add(profile)
    await db.flush()
    return profile


async def ensure_doctor_profile(
    db: AsyncSession,
    user: User,
    *,
    medical_council_number: Optional[str] = None,
    specialty: Optional[str] = None,
    verification_status: Optional[DoctorVerificationStatus] = None,
    verified_by_user_id: Optional[int] = None,
    verified_at: Optional[datetime] = None,
) -> DoctorProfile:
    result = await db.execute(
        select(DoctorProfile).where(DoctorProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    status = (
        verification_status
        or user.verification_status
        or DoctorVerificationStatus.PENDING
    )
    mcn = medical_council_number
    if mcn is None:
        mcn = user.medical_council_license
    spec = specialty if specialty is not None else user.specialty
    v_by = (
        verified_by_user_id
        if verified_by_user_id is not None
        else user.verified_by
    )
    v_at = verified_at if verified_at is not None else user.verified_at

    if profile is None:
        profile = DoctorProfile(
            user_id=user.id,
            medical_council_number=mcn,
            specialty=spec,
            verification_status=status,
            verified_by_user_id=v_by,
            verified_at=v_at,
        )
        db.add(profile)
    else:
        profile.medical_council_number = mcn
        profile.specialty = spec
        profile.verification_status = status
        profile.verified_by_user_id = v_by
        profile.verified_at = v_at
    await db.flush()
    return profile


async def ensure_staff_membership(
    db: AsyncSession,
    user: User,
    *,
    organization_id: Optional[UUID] = None,
) -> OrganizationMembership | None:
    if user.role not in (UserRole.DOCTOR, UserRole.ADMIN):
        return None
    org = await ensure_default_organization(db)
    org_id = organization_id or org.id
    result = await db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing
    role = (
        MembershipRole.DOCTOR
        if user.role == UserRole.DOCTOR
        else MembershipRole.ADMIN
    )
    membership = OrganizationMembership(
        organization_id=org_id,
        user_id=user.id,
        role=role,
        status=MembershipStatus.ACTIVE,
    )
    db.add(membership)
    await db.flush()
    return membership


async def sync_doctor_profile_from_user(db: AsyncSession, user: User) -> DoctorProfile:
    """Dual-write after mutating users.* doctor fields."""
    return await ensure_doctor_profile(db, user)


def consent_snapshot_for_enforcement() -> dict[str, str]:
    # Lazy import avoids circular: session_access → doctor_lifecycle → here → privacy.
    from app.privacy.consent_keys import ENFORCEMENT_REQUIRED_KEYS, current_version_for

    return {key: current_version_for(key) for key in ENFORCEMENT_REQUIRED_KEYS}


async def create_intake_encounter_for_patient(
    db: AsyncSession,
    *,
    patient: User,
    chief_complaint: Optional[str] = None,
    consent_snapshot: Optional[dict[str, Any]] = None,
) -> Encounter:
    org = await ensure_default_organization(db)
    now = datetime.now(timezone.utc)
    snapshot = (
        consent_snapshot
        if consent_snapshot is not None
        else consent_snapshot_for_enforcement()
    )
    encounter = Encounter(
        organization_id=org.id,
        subject_user_id=patient.id,
        subject_family_member_id=None,
        initiated_by_user_id=patient.id,
        consent_user_id=patient.id,
        consent_snapshot=snapshot,
        status=EncounterStatus.INTAKE,
        chief_complaint=chief_complaint,
        opened_at=now,
    )
    db.add(encounter)
    await db.flush()
    return encounter
