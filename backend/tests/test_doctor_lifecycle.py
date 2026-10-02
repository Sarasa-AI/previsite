"""Doctor verification lifecycle, session gates, and admin MFA actions."""

from __future__ import annotations

import pyotp
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken
from app.models.user import DoctorVerificationStatus, User, UserRole
from app.services import mfa_service, refresh_token_service
from tests.auth_helpers import national_id_from_seed, register_and_login_async
from tests.test_api_integration import _auth_headers, _national_id_from_seed


async def _create_admin(db: AsyncSession, *, suffix: str) -> User:
    admin = User(
        email=f"admin_{suffix}@test.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name=f"admin_{suffix}",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.flush()
    from app.services.platform_identity_service import ensure_staff_membership

    await ensure_staff_membership(db, admin)
    await db.commit()
    await db.refresh(admin)
    return admin


async def _create_doctor(
    db: AsyncSession,
    *,
    username: str,
    status: DoctorVerificationStatus = DoctorVerificationStatus.PENDING,
    password: str = "DoctorPass123!",
) -> User:
    doctor = User(
        email=f"{username}@doctor.com",
        hashed_password=get_password_hash(password),
        full_name=username,
        role=UserRole.DOCTOR,
        is_active=True,
        verification_status=status,
    )
    db.add(doctor)
    await db.flush()
    from app.services.platform_identity_service import (
        ensure_doctor_profile,
        ensure_staff_membership,
    )

    await ensure_doctor_profile(db, doctor)
    await ensure_staff_membership(db, doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def _login(client: AsyncClient, username: str, password: str) -> dict:
    response = await client.post(
        "/api/auth/login",
        json={"email": f"{username}@doctor.com" if "@" not in username else username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
async def client(db, test_db_engine):
    config_module.settings.single_doctor_mode = False
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    config_module.settings.single_doctor_mode = False


@pytest.mark.asyncio
async def test_admin_lists_doctors(db: AsyncSession, client: AsyncClient) -> None:
    admin = await _create_admin(db, suffix="list")
    await _create_doctor(db, username="doc_list_a", status=DoctorVerificationStatus.PENDING)
    await _create_doctor(db, username="doc_list_b", status=DoctorVerificationStatus.VERIFIED)

    token = create_access_token(data={"sub": str(admin.id), "email": admin.email})
    response = await client.get("/api/admin/doctors", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    ids = {item["full_name"] for item in response.json()}
    assert "doc_list_a" in ids
    assert "doc_list_b" in ids


@pytest.mark.asyncio
async def test_verify_suspend_reinstate_transitions(
    db: AsyncSession, client: AsyncClient
) -> None:
    admin = await _create_admin(db, suffix="lifecycle")
    doctor = await _create_doctor(db, username="doc_life", status=DoctorVerificationStatus.PENDING)
    admin_token = create_access_token(data={"sub": str(admin.id), "email": admin.email})

    verify = await client.post(
        f"/api/admin/doctors/{doctor.id}/verify",
        headers=_auth_headers(admin_token),
    )
    assert verify.status_code == 200
    assert verify.json()["verification_status"] == "verified"

    suspend = await client.post(
        f"/api/admin/doctors/{doctor.id}/suspend",
        headers=_auth_headers(admin_token),
    )
    assert suspend.status_code == 200
    assert suspend.json()["verification_status"] == "suspended"

    reinstate = await client.post(
        f"/api/admin/doctors/{doctor.id}/reinstate",
        headers=_auth_headers(admin_token),
    )
    assert reinstate.status_code == 200
    assert reinstate.json()["verification_status"] == "verified"

    logs = await db.execute(
        select(AuditLog.action).where(
            AuditLog.resource_type == "user",
            AuditLog.resource_id == str(doctor.id),
        )
    )
    actions = {row[0] for row in logs.all()}
    assert "doctor_verified" in actions
    assert "doctor_suspended" in actions
    assert "doctor_reinstated" in actions


@pytest.mark.asyncio
async def test_pending_doctor_denied_session_access(
    db: AsyncSession, client: AsyncClient
) -> None:
    await _create_doctor(db, username="doc_pending", status=DoctorVerificationStatus.PENDING)

    national_id = _national_id_from_seed("pending-gate-patient")
    patient_token = await register_and_login_async(
        client, national_id=national_id, password="VeryStrongPassword123!", seed=str(national_id)
    )
    session_resp = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth_headers(patient_token),
    )
    session_id = session_resp.json()["id"]

    doctor_login = await _login(client, "doc_pending", "DoctorPass123!")
    doctor_token = doctor_login["access_token"]

    denied = await client.get(
        f"/api/chat/{session_id}",
        headers=_auth_headers(doctor_token),
    )
    assert denied.status_code == 403

    listing = await client.get("/api/chat/sessions", headers=_auth_headers(doctor_token))
    assert listing.status_code == 200
    assert listing.json() == []


@pytest.mark.asyncio
async def test_suspended_doctor_cannot_claim_and_refresh_revoked(
    db: AsyncSession, client: AsyncClient
) -> None:
    admin = await _create_admin(db, suffix="suspend")
    doctor = await _create_doctor(db, username="doc_susp", status=DoctorVerificationStatus.VERIFIED)

    doctor_login = await _login(client, "doc_susp", "DoctorPass123!")
    refresh_raw = doctor_login["refresh_token"]
    assert refresh_raw

    admin_token = create_access_token(data={"sub": str(admin.id), "email": admin.email})
    suspend = await client.post(
        f"/api/admin/doctors/{doctor.id}/suspend",
        headers=_auth_headers(admin_token),
    )
    assert suspend.status_code == 200

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == doctor.id)
    )
    tokens = result.scalars().all()
    assert tokens
    assert all(t.revoked_at is not None for t in tokens)

    national_id = _national_id_from_seed("suspend-gate-patient")
    patient_token = await register_and_login_async(
        client, national_id=national_id, password="VeryStrongPassword123!", seed=str(national_id)
    )
    session_resp = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth_headers(patient_token),
    )
    session_id = session_resp.json()["id"]

    doctor_token = doctor_login["access_token"]
    claim_denied = await client.get(
        f"/api/chat/{session_id}",
        headers=_auth_headers(doctor_token),
    )
    assert claim_denied.status_code == 403

    rotate = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_raw},
    )
    assert rotate.status_code == 401


@pytest.mark.asyncio
async def test_verified_doctor_single_doctor_mode_unchanged(
    db: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "single_doctor_mode", True)
    await _create_doctor(db, username="doc_sdm", status=DoctorVerificationStatus.VERIFIED)

    national_id = _national_id_from_seed("sdm-patient")
    patient_token = await register_and_login_async(
        client, national_id=national_id, password="VeryStrongPassword123!", seed=str(national_id)
    )
    session_resp = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth_headers(patient_token),
    )
    session_id = session_resp.json()["id"]

    doctor_login = await _login(client, "doc_sdm", "DoctorPass123!")
    ok = await client.get(
        f"/api/chat/{session_id}",
        headers=_auth_headers(doctor_login["access_token"]),
    )
    assert ok.status_code == 200


@pytest.mark.asyncio
async def test_unverified_doctor_denied_even_in_single_doctor_mode(
    db: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "single_doctor_mode", True)
    await _create_doctor(db, username="doc_sdm_p", status=DoctorVerificationStatus.PENDING)

    national_id = _national_id_from_seed("sdm-pending-patient")
    patient_token = await register_and_login_async(
        client, national_id=national_id, password="VeryStrongPassword123!", seed=str(national_id)
    )
    session_resp = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth_headers(patient_token),
    )
    session_id = session_resp.json()["id"]

    doctor_login = await _login(client, "doc_sdm_p", "DoctorPass123!")
    denied = await client.get(
        f"/api/chat/{session_id}",
        headers=_auth_headers(doctor_login["access_token"]),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_admin_mfa_reset_revokes_refresh_families(
    db: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    admin = await _create_admin(db, suffix="mfa_reset")
    doctor = await _create_doctor(db, username="doc_mfa", status=DoctorVerificationStatus.VERIFIED)
    secret = mfa_service.generate_totp_secret()
    doctor.mfa_secret = secret
    doctor.mfa_enabled = True
    doctor.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(
        mfa_service.generate_backup_codes()
    )
    await db.commit()

    await refresh_token_service.issue_refresh_token(db, user_id=doctor.id)
    admin_token = create_access_token(data={"sub": str(admin.id), "email": admin.email})

    reset = await client.post(
        f"/api/admin/doctors/{doctor.id}/mfa/reset",
        headers=_auth_headers(admin_token),
    )
    assert reset.status_code == 200

    await db.refresh(doctor)
    assert doctor.mfa_enabled is False
    assert doctor.mfa_secret is None

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == doctor.id)
    )
    assert all(t.revoked_at is not None for t in result.scalars().all())


@pytest.mark.asyncio
async def test_admin_regenerates_backup_codes(
    db: AsyncSession, client: AsyncClient
) -> None:
    admin = await _create_admin(db, suffix="backup")
    doctor = await _create_doctor(db, username="doc_backup", status=DoctorVerificationStatus.VERIFIED)
    doctor.mfa_secret = mfa_service.generate_totp_secret()
    doctor.mfa_enabled = True
    doctor.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(["aaaa"])
    await db.commit()

    admin_token = create_access_token(data={"sub": str(admin.id), "email": admin.email})
    regen = await client.post(
        f"/api/admin/doctors/{doctor.id}/mfa/regenerate-backup-codes",
        headers=_auth_headers(admin_token),
    )
    assert regen.status_code == 200
    codes = regen.json()["backup_codes"]
    assert len(codes) == 10


@pytest.mark.asyncio
async def test_doctor_mfa_required_flag(
    db: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "doctor_mfa_required", True)
    monkeypatch.setattr(config_module.settings, "mfa_enabled", False)
    await _create_doctor(db, username="doc_dmfa", status=DoctorVerificationStatus.VERIFIED)

    login = await client.post(
        "/api/auth/login",
        json={"email": "doc_dmfa@doctor.com", "password": "DoctorPass123!"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body.get("mfa_setup_required") is True


@pytest.mark.asyncio
async def test_admin_mfa_required_flag(
    db: AsyncSession, client: AsyncClient, monkeypatch
) -> None:
    monkeypatch.setattr(config_module.settings, "admin_mfa_required", True)
    admin = await _create_admin(db, suffix="adm_mfa")
    login = await client.post(
        "/api/auth/login",
        json={"email": admin.email, "password": "AdminPass123!"},
    )
    assert login.status_code == 200
    assert login.json().get("mfa_setup_required") is True


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_doctors(db: AsyncSession, client: AsyncClient) -> None:
    doctor = await _create_doctor(db, username="doc_no_admin", status=DoctorVerificationStatus.VERIFIED)
    token = create_access_token(data={"sub": str(doctor.id), "email": doctor.email})
    response = await client.get("/api/admin/doctors", headers=_auth_headers(token))
    assert response.status_code == 403
