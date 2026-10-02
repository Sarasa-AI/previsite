"""P3 foundation — Encounter, profiles, org membership, erasure."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.models import (
    DEFAULT_ORGANIZATION_ID,
    Encounter,
    EncounterStatus,
    FamilyGroup,
    FamilyMember,
    OrganizationMembership,
    PatientProfile,
    Session,
    User,
)
from app.models.account_deletion_request import (
    AccountDeletionRequest,
    DeletionRequestStatus,
)
from app.models.doctor_profile import DoctorProfile
from app.models.user import DoctorVerificationStatus, UserRole
from app.privacy.erasure_service import execute_approved_deletion
from app.services.otp_service import _create_patient_for_phone
from app.services.platform_identity_service import (
    create_intake_encounter_for_patient,
    ensure_default_organization,
    ensure_doctor_profile,
    ensure_patient_profile,
    ensure_staff_membership,
)
from tests.auth_helpers import phone_from_seed
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _create_patient(db: AsyncSession, *, seed: str) -> User:
    national_id = _national_id_from_seed(seed)
    user = User(
        email=f"p3_{national_id}@patient.local",
        hashed_password=get_password_hash("PatientPass123!"),
        full_name=f"بیمار {national_id[-4:]}",
        national_id=national_id,
        phone=phone_from_seed(seed),
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await ensure_patient_profile(db, user)
    await db.commit()
    await db.refresh(user)
    return user


def _patient_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return _auth_headers(token)


@pytest.mark.asyncio
async def test_otp_patient_gets_patient_profile(db: AsyncSession):
    phone = phone_from_seed("p3-otp-profile")
    user = await _create_patient_for_phone(db, phone=phone)
    result = await db.execute(
        select(PatientProfile).where(PatientProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    assert profile is not None
    assert profile.deleted_at is None


@pytest.mark.asyncio
async def test_default_organization_seeded_via_ensure(db: AsyncSession):
    org = await ensure_default_organization(db)
    await db.commit()
    assert org.id == DEFAULT_ORGANIZATION_ID
    assert org.slug == "previsit"
    assert org.is_default is True


@pytest.mark.asyncio
async def test_doctor_dual_write_profile_and_membership(db: AsyncSession):
    await ensure_default_organization(db)
    doctor = User(
        email="p3_doctor@clinic.local",
        hashed_password=get_password_hash("DoctorPass123!"),
        full_name="P3 Doctor",
        role=UserRole.DOCTOR,
        is_active=True,
        medical_council_license="12345",
        specialty="IM",
        verification_status=DoctorVerificationStatus.PENDING,
    )
    db.add(doctor)
    await db.flush()
    await ensure_doctor_profile(db, doctor)
    await ensure_staff_membership(db, doctor)
    await db.commit()

    profile = (
        await db.execute(
            select(DoctorProfile).where(DoctorProfile.user_id == doctor.id)
        )
    ).scalar_one()
    assert profile.medical_council_number == "12345"
    assert profile.verification_status == DoctorVerificationStatus.PENDING

    membership = (
        await db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == doctor.id
            )
        )
    ).scalar_one()
    assert membership.organization_id == DEFAULT_ORGANIZATION_ID
    assert membership.role.value == "doctor"


@pytest.mark.asyncio
async def test_create_session_links_encounter(
    async_client: AsyncClient, db: AsyncSession
):
    await ensure_default_organization(db)
    await db.commit()
    patient = await _create_patient(db, seed="p3-session-enc")

    response = await async_client.post(
        "/api/chat/session",
        headers=_patient_headers(patient),
        json={"initial_complaint": "سردرد"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "id" in body
    assert body.get("initial_complaint") == "سردرد"
    # Response shape unchanged — no encounter_id exposed.
    assert "encounter_id" not in body

    sess = (
        await db.execute(select(Session).where(Session.id == body["id"]))
    ).scalar_one()
    assert sess.encounter_id is not None
    assert sess.organization_id == DEFAULT_ORGANIZATION_ID

    enc = (
        await db.execute(
            select(Encounter).where(Encounter.id == sess.encounter_id)
        )
    ).scalar_one()
    assert enc.status == EncounterStatus.INTAKE
    assert enc.subject_user_id == patient.id
    assert enc.subject_family_member_id is None
    assert enc.chief_complaint == "سردرد"
    assert enc.signed_at is None
    assert enc.consent_snapshot is not None


@pytest.mark.asyncio
async def test_encounter_subject_xor_rejects_both(db: AsyncSession):
    await ensure_default_organization(db)
    patient = await _create_patient(db, seed="p3-xor-both")
    group = FamilyGroup(owner_user_id=patient.id)
    db.add(group)
    await db.flush()
    member = FamilyMember(
        family_group_id=group.id,
        display_name="فرزند",
        relationship_to_owner="child",
    )
    db.add(member)
    await db.flush()

    enc = Encounter(
        organization_id=DEFAULT_ORGANIZATION_ID,
        subject_user_id=patient.id,
        subject_family_member_id=member.id,
        initiated_by_user_id=patient.id,
        consent_user_id=patient.id,
        status=EncounterStatus.INTAKE,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(enc)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_encounter_subject_xor_rejects_neither(db: AsyncSession):
    await ensure_default_organization(db)
    patient = await _create_patient(db, seed="p3-xor-none")
    enc = Encounter(
        organization_id=DEFAULT_ORGANIZATION_ID,
        subject_user_id=None,
        subject_family_member_id=None,
        initiated_by_user_id=patient.id,
        consent_user_id=patient.id,
        status=EncounterStatus.INTAKE,
        opened_at=datetime.now(timezone.utc),
    )
    db.add(enc)
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_one_live_family_group_per_owner(db: AsyncSession):
    patient = await _create_patient(db, seed="p3-family-unique")
    db.add(FamilyGroup(owner_user_id=patient.id))
    await db.commit()
    db.add(FamilyGroup(owner_user_id=patient.id))
    with pytest.raises(IntegrityError):
        await db.commit()
    await db.rollback()


@pytest.mark.asyncio
async def test_backfill_style_session_to_encounter_status_map(db: AsyncSession):
    """Simulate migration mapping: completed → closed, never signed."""
    await ensure_default_organization(db)
    patient = await _create_patient(db, seed="p3-backfill-map")
    enc = Encounter(
        organization_id=DEFAULT_ORGANIZATION_ID,
        subject_user_id=patient.id,
        initiated_by_user_id=patient.id,
        consent_user_id=patient.id,
        status=EncounterStatus.CLOSED,
        chief_complaint="legacy",
        opened_at=datetime.now(timezone.utc),
        consent_snapshot=None,
        signed_at=None,
    )
    db.add(enc)
    await db.flush()
    sess = Session(
        patient_id=patient.id,
        status="completed",
        encounter_id=enc.id,
        organization_id=DEFAULT_ORGANIZATION_ID,
        initial_complaint="legacy",
    )
    db.add(sess)
    await db.commit()

    loaded = (
        await db.execute(select(Encounter).where(Encounter.id == enc.id))
    ).scalar_one()
    assert loaded.status == EncounterStatus.CLOSED
    assert loaded.signed_at is None


@pytest.mark.asyncio
async def test_erasure_shell_clears_encounter_fields(db: AsyncSession):
    previous = config_module.settings.legal_retention_keep_session_shell
    config_module.settings.legal_retention_keep_session_shell = True
    try:
        await ensure_default_organization(db)
        patient = await _create_patient(db, seed="p3-erase-shell")
        enc = await create_intake_encounter_for_patient(
            db, patient=patient, chief_complaint="pain"
        )
        group = FamilyGroup(owner_user_id=patient.id)
        db.add(group)
        await db.flush()
        member = FamilyMember(
            family_group_id=group.id,
            display_name="کودک",
            relationship_to_owner="child",
        )
        db.add(member)
        await db.flush()
        dep_enc = Encounter(
            organization_id=DEFAULT_ORGANIZATION_ID,
            subject_family_member_id=member.id,
            initiated_by_user_id=patient.id,
            consent_user_id=patient.id,
            status=EncounterStatus.INTAKE,
            chief_complaint="fever",
            consent_snapshot={"ai_processing": "v1"},
            opened_at=datetime.now(timezone.utc),
        )
        db.add(dep_enc)
        req = AccountDeletionRequest(
            user_id=patient.id,
            status=DeletionRequestStatus.APPROVED,
            requested_at=datetime.now(timezone.utc),
            cool_off_until=datetime.now(timezone.utc),
            approved_at=datetime.now(timezone.utc),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        await execute_approved_deletion(db, req.id)

        await db.refresh(enc)
        await db.refresh(dep_enc)
        await db.refresh(group)
        await db.refresh(member)
        profile = (
            await db.execute(
                select(PatientProfile).where(PatientProfile.user_id == patient.id)
            )
        ).scalar_one()

        assert enc.chief_complaint is None
        assert enc.consent_snapshot is None
        assert enc.deleted_at is None
        assert dep_enc.chief_complaint is None
        assert dep_enc.consent_snapshot is None
        assert dep_enc.deleted_at is None
        assert group.deleted_at is not None
        assert member.deleted_at is not None
        assert profile.deleted_at is not None
    finally:
        config_module.settings.legal_retention_keep_session_shell = previous


@pytest.mark.asyncio
async def test_erasure_soft_deletes_encounter_when_no_shell(db: AsyncSession):
    previous = config_module.settings.legal_retention_keep_session_shell
    config_module.settings.legal_retention_keep_session_shell = False
    try:
        await ensure_default_organization(db)
        patient = await _create_patient(db, seed="p3-erase-soft")
        enc = await create_intake_encounter_for_patient(
            db, patient=patient, chief_complaint="pain"
        )
        req = AccountDeletionRequest(
            user_id=patient.id,
            status=DeletionRequestStatus.APPROVED,
            requested_at=datetime.now(timezone.utc),
            cool_off_until=datetime.now(timezone.utc),
            approved_at=datetime.now(timezone.utc),
        )
        db.add(req)
        await db.commit()
        await db.refresh(req)

        await execute_approved_deletion(db, req.id)
        await db.refresh(enc)
        assert enc.deleted_at is not None
    finally:
        config_module.settings.legal_retention_keep_session_shell = previous


@pytest.mark.asyncio
async def test_encounter_indexes_exist_on_metadata():
    """ORM declares the mandatory composite/subject/doctor indexes."""
    index_names = {idx.name for idx in Encounter.__table__.indexes}
    assert "ix_encounters_org_status" in index_names
    assert "ix_encounters_subject_user" in index_names
    assert "ix_encounters_subject_family_member" in index_names
    assert "ix_encounters_doctor_user" in index_names
    uq_names = {
        c.name for c in OrganizationMembership.__table__.constraints if c.name
    }
    assert "uq_organization_memberships_org_user" in uq_names
