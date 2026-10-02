"""Doctor MFA / TOTP enrollment and login challenge tests."""

from __future__ import annotations

import pyotp
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_password_hash
from app.core import config as config_module
from app.models.user import DoctorVerificationStatus, User, UserRole
from app.services import mfa_service


@pytest.fixture
def enable_mfa(monkeypatch):
    monkeypatch.setenv("MFA_ENABLED", "true")
    config_module.settings.mfa_enabled = True
    yield
    config_module.settings.mfa_enabled = False


async def _create_doctor(db: AsyncSession, *, username: str = "mfa_doc") -> User:
    doctor = User(
        email=f"{username}@doctor.com",
        hashed_password=get_password_hash("DoctorPass123!"),
        full_name=username,
        role=UserRole.DOCTOR,
        is_active=True,
        verification_status=DoctorVerificationStatus.VERIFIED,
        mfa_enabled=False,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


@pytest.mark.asyncio
async def test_login_requires_mfa_setup_when_flag_on(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    await _create_doctor(db, username="setup_doc")
    response = await async_client.post(
        "/api/auth/login",
        json={"email": "setup_doc@doctor.com", "password": "DoctorPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mfa_setup_required"] is True
    assert body.get("access_token") in (None, "")
    assert body["setup_token"]
    assert body["otpauth_uri"].startswith("otpauth://")


@pytest.mark.asyncio
async def test_login_without_totp_rejected_when_mfa_enabled(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    doctor = await _create_doctor(db, username="chal_doc")
    secret = mfa_service.generate_totp_secret()
    doctor.mfa_secret = secret
    doctor.mfa_enabled = True
    doctor.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(
        mfa_service.generate_backup_codes()
    )
    await db.commit()

    response = await async_client.post(
        "/api/auth/login",
        json={"email": "chal_doc@doctor.com", "password": "DoctorPass123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mfa_required"] is True
    assert not body.get("access_token")
    assert body["mfa_token"]


@pytest.mark.asyncio
async def test_mfa_verify_with_valid_totp(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    doctor = await _create_doctor(db, username="totp_doc")
    secret = mfa_service.generate_totp_secret()
    doctor.mfa_secret = secret
    doctor.mfa_enabled = True
    await db.commit()

    login = await async_client.post(
        "/api/auth/login",
        json={"email": "totp_doc@doctor.com", "password": "DoctorPass123!"},
    )
    mfa_token = login.json()["mfa_token"]
    code = pyotp.TOTP(secret).now()

    verify = await async_client.post(
        "/api/auth/mfa/verify",
        json={"mfa_token": mfa_token, "code": code},
    )
    assert verify.status_code == 200
    assert verify.json()["access_token"]


@pytest.mark.asyncio
async def test_backup_code_is_single_use(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    doctor = await _create_doctor(db, username="backup_doc")
    secret = mfa_service.generate_totp_secret()
    codes = mfa_service.generate_backup_codes()
    doctor.mfa_secret = secret
    doctor.mfa_enabled = True
    doctor.mfa_backup_codes_hash = mfa_service.serialize_backup_hashes(codes)
    await db.commit()

    login = await async_client.post(
        "/api/auth/login",
        json={"email": "backup_doc@doctor.com", "password": "DoctorPass123!"},
    )
    mfa_token = login.json()["mfa_token"]
    first = await async_client.post(
        "/api/auth/mfa/verify",
        json={"mfa_token": mfa_token, "code": codes[0]},
    )
    assert first.status_code == 200
    assert first.json()["access_token"]

    login2 = await async_client.post(
        "/api/auth/login",
        json={"email": "backup_doc@doctor.com", "password": "DoctorPass123!"},
    )
    mfa_token2 = login2.json()["mfa_token"]
    second = await async_client.post(
        "/api/auth/mfa/verify",
        json={"mfa_token": mfa_token2, "code": codes[0]},
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_setup_verify_enables_mfa_and_returns_backup_codes(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    await _create_doctor(db, username="enroll_doc")
    login = await async_client.post(
        "/api/auth/login",
        json={"email": "enroll_doc@doctor.com", "password": "DoctorPass123!"},
    )
    body = login.json()
    # Extract secret from otpauth URI
    uri = body["otpauth_uri"]
    secret = uri.split("secret=")[1].split("&")[0]
    code = pyotp.TOTP(secret).now()

    setup = await async_client.post(
        "/api/auth/mfa/setup/verify",
        json={"setup_token": body["setup_token"], "code": code},
    )
    assert setup.status_code == 200
    payload = setup.json()
    assert payload["access_token"]
    assert len(payload["backup_codes"]) == 10

    # Subsequent login now requires MFA challenge
    again = await async_client.post(
        "/api/auth/login",
        json={"email": "enroll_doc@doctor.com", "password": "DoctorPass123!"},
    )
    assert again.json()["mfa_required"] is True


@pytest.mark.asyncio
async def test_setup_token_contains_no_secret_material(
    async_client: AsyncClient, db: AsyncSession, enable_mfa
) -> None:
    await _create_doctor(db, username="nosecret_doc")
    login = await async_client.post(
        "/api/auth/login",
        json={"email": "nosecret_doc@doctor.com", "password": "DoctorPass123!"},
    )
    body = login.json()
    assert body["mfa_setup_required"] is True
    from app.auth.security import decode_access_token

    payload = decode_access_token(body["setup_token"])
    assert payload is not None
    assert "mfa_secret" not in payload
    assert "secret" not in payload
    assert payload.get("challenge_id")
    # otpauth URI still returned for QR; secret must not appear in the token
    uri_secret = body["otpauth_uri"].split("secret=")[1].split("&")[0]
    token_str = body["setup_token"]
    assert uri_secret not in token_str


@pytest.mark.asyncio
async def test_setup_challenge_expired_and_reuse_fail(
    async_client: AsyncClient, db: AsyncSession, enable_mfa, monkeypatch
) -> None:
    from datetime import datetime, timedelta, timezone

    from app.models.mfa_setup_challenge import MfaSetupChallenge

    await _create_doctor(db, username="expire_doc")
    login = await async_client.post(
        "/api/auth/login",
        json={"email": "expire_doc@doctor.com", "password": "DoctorPass123!"},
    )
    body = login.json()
    uri = body["otpauth_uri"]
    secret = uri.split("secret=")[1].split("&")[0]
    code = pyotp.TOTP(secret).now()
    setup_token = body["setup_token"]

    from app.auth.security import decode_access_token

    challenge_id = decode_access_token(setup_token)["challenge_id"]
    row = await db.get(MfaSetupChallenge, challenge_id)
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await db.commit()

    expired = await async_client.post(
        "/api/auth/mfa/setup/verify",
        json={"setup_token": setup_token, "code": code},
    )
    assert expired.status_code == 401

    # Fresh challenge for reuse test
    login2 = await async_client.post(
        "/api/auth/login",
        json={"email": "expire_doc@doctor.com", "password": "DoctorPass123!"},
    )
    body2 = login2.json()
    uri2 = body2["otpauth_uri"]
    secret2 = uri2.split("secret=")[1].split("&")[0]
    code2 = pyotp.TOTP(secret2).now()
    token2 = body2["setup_token"]

    first = await async_client.post(
        "/api/auth/mfa/setup/verify",
        json={"setup_token": token2, "code": code2},
    )
    assert first.status_code == 200, first.text

    reused = await async_client.post(
        "/api/auth/mfa/setup/verify",
        json={"setup_token": token2, "code": code2},
    )
    assert reused.status_code == 401
