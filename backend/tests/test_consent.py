"""P2-A consent records: grant/withdraw history, version bump, enforcement, authz."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.models.audit_log import AuditLog
from app.models.patient_consent import PatientConsent
from app.models.session import Session
from app.models.user import DoctorVerificationStatus, User, UserRole
from app.privacy.consent_keys import (
    AI_PROCESSING,
    DATA_PROCESSING,
    ENFORCEMENT_REQUIRED_KEYS,
)
from app.services.audit_service import AUDIT_CONSENT_PATIENT_READ
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _create_patient(
    db: AsyncSession, *, seed: str = "consent_patient"
) -> User:
    national_id = _national_id_from_seed(seed)
    user = User(
        email=f"patient_{national_id}@patient.local",
        hashed_password=get_password_hash("PatientPass123!"),
        full_name=f"بیمار {national_id[-4:]}",
        national_id=national_id,
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_doctor(
    db: AsyncSession, *, username: str = "consent_doc"
) -> User:
    user = User(
        email=f"{username}@clinic.local",
        hashed_password=get_password_hash("DoctorPass123!"),
        full_name=username,
        role=UserRole.DOCTOR,
        is_active=True,
        verification_status=DoctorVerificationStatus.VERIFIED,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def _patient_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": str(user.id), "email": user.email})
    return _auth_headers(token)


@pytest.mark.asyncio
async def test_grant_withdraw_append_only_history(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    patient = await _create_patient(db)
    headers = _patient_headers(patient)

    grant = await async_client.post(
        "/api/consent/grant",
        headers=headers,
        json={"consent_key": AI_PROCESSING},
    )
    assert grant.status_code == 200, grant.text
    grant_body = grant.json()
    assert grant_body["granted"] is True
    assert grant_body["policy_version"] == "v1"
    assert grant_body["granted_at"] is not None
    assert grant_body["withdrawn_at"] is None
    grant_id = grant_body["id"]

    withdraw = await async_client.post(
        "/api/consent/withdraw",
        headers=headers,
        json={"consent_key": AI_PROCESSING},
    )
    assert withdraw.status_code == 200, withdraw.text
    withdraw_body = withdraw.json()
    assert withdraw_body["id"] != grant_id
    assert withdraw_body["granted"] is False
    assert withdraw_body["withdrawn_at"] is not None

    # Original grant row must remain unchanged (append-only).
    original = (
        await db.execute(select(PatientConsent).where(PatientConsent.id == grant_id))
    ).scalar_one()
    assert original.granted is True
    assert original.withdrawn_at is None

    history = await async_client.get("/api/consent/me/history", headers=headers)
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 2
    assert rows[0]["id"] == grant_id
    assert rows[1]["id"] == withdraw_body["id"]

    status = await async_client.get("/api/consent/me", headers=headers)
    assert status.status_code == 200
    body = status.json()
    ai = next(c for c in body["consents"] if c["consent_key"] == AI_PROCESSING)
    assert ai["granted"] is False
    assert ai["copy_text_key"] == "consent.copy.ai_processing.v1"


@pytest.mark.asyncio
async def test_version_bump_invalidates_old_consent(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    patient = await _create_patient(db, seed="consent_version")
    headers = _patient_headers(patient)

    grant = await async_client.post(
        "/api/consent/grant",
        headers=headers,
        json={"consent_key": DATA_PROCESSING, "policy_version": "v1"},
    )
    assert grant.status_code == 200

    status_before = await async_client.get("/api/consent/me", headers=headers)
    data = next(
        c
        for c in status_before.json()["consents"]
        if c["consent_key"] == DATA_PROCESSING
    )
    assert data["granted"] is True

    monkeypatch.setattr(
        config_module.settings, "consent_version_data_processing", "v2"
    )

    status_after = await async_client.get("/api/consent/me", headers=headers)
    data_after = next(
        c
        for c in status_after.json()["consents"]
        if c["consent_key"] == DATA_PROCESSING
    )
    assert data_after["granted"] is False
    assert data_after["policy_version"] == "v2"
    assert data_after["latest_policy_version"] == "v1"
    assert data_after["copy_text_key"] == "consent.copy.data_processing.v2"


@pytest.mark.asyncio
async def test_enforcement_off_allows_session_create(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "consent_enforcement_enabled", False)
    patient = await _create_patient(db, seed="consent_off")
    headers = _patient_headers(patient)

    response = await async_client.post(
        "/api/chat/session",
        headers=headers,
        json={"initial_complaint": "سردرد"},
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_enforcement_on_blocks_without_consents(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "consent_enforcement_enabled", True)
    patient = await _create_patient(db, seed="consent_on_block")
    headers = _patient_headers(patient)

    response = await async_client.post(
        "/api/chat/session",
        headers=headers,
        json={"initial_complaint": "سردرد"},
    )
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail["code"] == "CONSENT_REQUIRED"
    assert set(detail["missing"]) == set(ENFORCEMENT_REQUIRED_KEYS)


@pytest.mark.asyncio
async def test_enforcement_on_allows_after_required_grants(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "consent_enforcement_enabled", True)
    patient = await _create_patient(db, seed="consent_on_ok")
    headers = _patient_headers(patient)

    for key in ENFORCEMENT_REQUIRED_KEYS:
        granted = await async_client.post(
            "/api/consent/grant",
            headers=headers,
            json={"consent_key": key},
        )
        assert granted.status_code == 200, granted.text

    response = await async_client.post(
        "/api/chat/session",
        headers=headers,
        json={"initial_complaint": "سردرد"},
    )
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_enforcement_blocks_intake_write(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "consent_enforcement_enabled", False)
    patient = await _create_patient(db, seed="consent_intake")
    headers = _patient_headers(patient)

    session_resp = await async_client.post(
        "/api/chat/session",
        headers=headers,
        json={"initial_complaint": "درد"},
    )
    assert session_resp.status_code == 200
    session_id = session_resp.json()["id"]

    monkeypatch.setattr(config_module.settings, "consent_enforcement_enabled", True)

    blocked = await async_client.post(
        f"/api/intake/{session_id}/layer1",
        headers=headers,
        json={
            "first_name": "علی",
            "last_name": "تست",
            "national_id": patient.national_id,
            "insurance_provider": "test",
            "age": 30,
            "sex": "male",
            "weight": 70.0,
            "height": 170.0,
            "chief_complaint": "درد",
        },
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "CONSENT_REQUIRED"


@pytest.mark.asyncio
async def test_doctor_can_read_authorized_patient_consents(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "single_doctor_mode", False)
    patient = await _create_patient(db, seed="consent_authz_p")
    doctor = await _create_doctor(db, username="consent_authz_d")
    other_doctor = await _create_doctor(db, username="consent_authz_other")

    session = Session(
        patient_id=patient.id,
        doctor_id=doctor.id,
        status="active",
        initial_complaint="test",
    )
    db.add(session)
    await db.commit()

    await async_client.post(
        "/api/consent/grant",
        headers=_patient_headers(patient),
        json={"consent_key": AI_PROCESSING},
    )

    doctor_token = create_access_token(
        data={"sub": str(doctor.id), "email": doctor.email}
    )
    ok = await async_client.get(
        f"/api/consent/patient/{patient.id}",
        headers=_auth_headers(doctor_token),
    )
    assert ok.status_code == 200, ok.text
    assert any(
        c["consent_key"] == AI_PROCESSING and c["granted"]
        for c in ok.json()["consents"]
    )

    audits = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_CONSENT_PATIENT_READ)
        )
    ).scalars().all()
    assert any(a.user_id == doctor.id for a in audits)

    other_token = create_access_token(
        data={"sub": str(other_doctor.id), "email": other_doctor.email}
    )
    denied = await async_client.get(
        f"/api/consent/patient/{patient.id}",
        headers=_auth_headers(other_token),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_doctor_cannot_grant_patient_consents(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    doctor = await _create_doctor(db, username="consent_no_grant")
    token = create_access_token(
        data={"sub": str(doctor.id), "email": doctor.email}
    )
    response = await async_client.post(
        "/api/consent/grant",
        headers=_auth_headers(token),
        json={"consent_key": AI_PROCESSING},
    )
    assert response.status_code == 403
