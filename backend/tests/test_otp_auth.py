"""OTP auth lifecycle tests — TestSmsProvider only; never send real SMS."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core import config as config_module
from app.core.rate_limiter import rate_limiter
from app.db import database as database_module
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.otp_challenge import OtpChallenge
from app.models.user import User, UserRole
from app.auth.security import get_password_hash
from app.services.sms import get_test_sms_provider, reset_test_sms_provider
from app.utils.national_id import validate_iranian_national_id
from tests.conftest import setup_async_test_db, teardown_test_db


FAKE_PHONE = "+989121234567"
FAKE_PHONE_ALT = "+989121234568"


def _create_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("SMS_PROVIDER", "test")
    config_module.settings.sms_provider = "test"
    config_module.settings.otp_login_enabled = True
    config_module.settings.legacy_patient_password_login_enabled = True
    reset_test_sms_provider()
    rate_limiter.reset()

    engine = asyncio.run(setup_async_test_db(tmp_path, monkeypatch))
    client = TestClient(fastapi_app)

    def cleanup():
        teardown_test_db()
        asyncio.run(engine.dispose())
        client.close()

    client._async_cleanup = cleanup  # type: ignore[attr-defined]
    return client


def _national_id_from_seed(seed: str) -> str:
    candidate = 1_000_000_000 + (abs(hash(seed)) % 900_000_000)
    while candidate < 9_999_999_999:
        national_id = str(candidate).zfill(10)
        if validate_iranian_national_id(national_id):
            return national_id
        candidate += 1
    return "0499370899"


def _last_otp(phone: str = FAKE_PHONE) -> str:
    code = get_test_sms_provider().last_code_for(phone)
    assert code is not None
    return code


def test_otp_lifecycle_creates_patient(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        req = client.post("/api/auth/otp/request", json={"phone": "09121234567"})
        assert req.status_code == 200, req.text
        body = req.json()
        assert body["success"] is True
        assert "cooldown_seconds" in body
        assert "code" not in body
        assert FAKE_PHONE not in req.text

        code = _last_otp()
        ver = client.post(
            "/api/auth/otp/verify",
            json={"phone": "09121234567", "code": code},
        )
        assert ver.status_code == 200, ver.text
        token = ver.json()
        assert token.get("access_token")
        assert token.get("refresh_token")

        # Second verify with same code fails (single use)
        ver2 = client.post(
            "/api/auth/otp/verify",
            json={"phone": "09121234567", "code": code},
        )
        assert ver2.status_code == 401

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["role"] == "patient"
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_otp_role_forced_patient(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        code = _last_otp()
        ver = client.post(
            "/api/auth/otp/verify", json={"phone": FAKE_PHONE, "code": code}
        )
        assert ver.json()["access_token"]

        async def _check():
            async with database_module.AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.phone == FAKE_PHONE))
                user = result.scalar_one()
                assert user.role == UserRole.PATIENT
                assert user.hashed_password is None

        asyncio.run(_check())
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_otp_expiry(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    config_module.settings.otp_ttl_seconds = 120
    try:
        client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        code = _last_otp()

        async def _expire():
            async with database_module.AsyncSessionLocal() as db:
                result = await db.execute(
                    select(OtpChallenge)
                    .where(OtpChallenge.phone == FAKE_PHONE)
                    .order_by(OtpChallenge.created_at.desc())
                )
                challenge = result.scalars().first()
                assert challenge
                challenge.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
                await db.commit()

        asyncio.run(_expire())
        ver = client.post(
            "/api/auth/otp/verify", json={"phone": FAKE_PHONE, "code": code}
        )
        assert ver.status_code == 401
        assert ver.json()["detail"] == "OTP_EXPIRED"
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_otp_attempt_lockout(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    config_module.settings.otp_max_attempts = 5
    try:
        client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        for _ in range(5):
            bad = client.post(
                "/api/auth/otp/verify",
                json={"phone": FAKE_PHONE, "code": "000000"},
            )
        assert bad.status_code == 429
        assert bad.json()["detail"] == "OTP_LOCKED"

        code = _last_otp()
        ver = client.post(
            "/api/auth/otp/verify", json={"phone": FAKE_PHONE, "code": code}
        )
        assert ver.status_code == 429
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_otp_cooldown(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    config_module.settings.otp_resend_cooldown_seconds = 60
    try:
        r1 = client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        assert r1.status_code == 200
        r2 = client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        assert r2.status_code == 429
        assert r2.json()["detail"] == "OTP_COOLDOWN"
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_otp_enumeration_safe_response(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        # Unknown phone
        r1 = client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        # Known phone (after create)
        code = _last_otp()
        client.post("/api/auth/otp/verify", json={"phone": FAKE_PHONE, "code": code})
        rate_limiter.reset()
        reset_test_sms_provider()
        r2 = client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
        assert r1.status_code == r2.status_code == 200
        assert set(r1.json().keys()) == set(r2.json().keys())
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_no_code_or_full_phone_in_audit(tmp_path, monkeypatch, caplog) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        with caplog.at_level(logging.INFO):
            client.post("/api/auth/otp/request", json={"phone": FAKE_PHONE})
            code = _last_otp()
            client.post(
                "/api/auth/otp/verify", json={"phone": FAKE_PHONE, "code": code}
            )

        joined = " ".join(r.message for r in caplog.records)
        assert code not in joined
        assert "9121234567" not in joined  # unmasked full local form

        async def _audits():
            async with database_module.AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AuditLog).where(AuditLog.action.like("otp_%"))
                )
                rows = result.scalars().all()
                assert rows
                for row in rows:
                    rid = str(row.resource_id or "")
                    assert code not in rid
                    assert FAKE_PHONE not in rid
                    assert "9121234567" not in rid

        asyncio.run(_audits())
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_startup_fail_fast_production_console_sms(monkeypatch) -> None:
    from app.core.config import validate_startup_config

    monkeypatch.setattr(config_module.settings, "app_env", "production")
    monkeypatch.setattr(config_module.settings, "otp_login_enabled", True)
    monkeypatch.setattr(config_module.settings, "sms_provider", "console")
    monkeypatch.setattr(
        config_module.settings, "secret_key", "production-secret-key-32chars!!"
    )
    monkeypatch.setattr(config_module.settings, "db_password", "strong-db-pass")
    monkeypatch.setattr(config_module.settings, "s3_access_key", "prod-access")
    monkeypatch.setattr(config_module.settings, "s3_secret_key", "prod-secret")
    monkeypatch.setattr(config_module.settings, "seed_doctor_password", "DoctorPass!")
    with pytest.raises(SystemExit) as exc:
        validate_startup_config()
    assert "SMS_PROVIDER" in str(exc.value)


def test_full_name_login_rejected(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        # Seed doctor has full_name == username; must not login by full name.
        r = client.post(
            "/api/auth/login",
            json={"national_id": "bagherzade", "password": "0808"},
        )
        # national_id path requires valid Iranian ID — invalid ID → credentials fail
        assert r.status_code in (401, 403)
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_doctor_email_login_works(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    try:
        r = client.post(
            "/api/auth/login",
            json={"email": "bagherzade@doctor.com", "password": "0808"},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("access_token")
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_legacy_patient_phone_link(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    nid = _national_id_from_seed("legacy-link")
    password = "LegacyPass123!"

    async def _seed():
        async with database_module.AsyncSessionLocal() as db:
            user = User(
                email=f"patient_{nid}@patient.local",
                full_name=f"بیمار {nid[-4:]}",
                national_id=nid,
                phone=None,
                hashed_password=get_password_hash(password),
                role=UserRole.PATIENT,
                is_active=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user.id

    user_id = asyncio.run(_seed())
    try:
        login = client.post(
            "/api/auth/login",
            json={"national_id": nid, "password": password},
        )
        assert login.status_code == 200, login.text
        body = login.json()
        assert body.get("phone_link_required") is True
        assert body.get("code") == "PHONE_LINK_REQUIRED"
        assert body.get("link_token")
        assert not body.get("access_token")

        link_token = body["link_token"]
        req = client.post(
            "/api/auth/otp/request",
            json={"phone": FAKE_PHONE_ALT, "link_token": link_token},
        )
        assert req.status_code == 200, req.text
        code = _last_otp(FAKE_PHONE_ALT)
        ver = client.post(
            "/api/auth/otp/verify",
            json={
                "phone": FAKE_PHONE_ALT,
                "code": code,
                "link_token": link_token,
            },
        )
        assert ver.status_code == 200, ver.text
        assert ver.json().get("access_token")

        async def _check():
            async with database_module.AsyncSessionLocal() as db:
                result = await db.execute(select(User).where(User.id == user_id))
                user = result.scalar_one()
                assert user.phone == FAKE_PHONE_ALT
                assert user.national_id == nid

        asyncio.run(_check())
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_legacy_login_disabled(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    config_module.settings.legacy_patient_password_login_enabled = False
    nid = _national_id_from_seed("legacy-off")
    try:
        r = client.post(
            "/api/auth/login",
            json={"national_id": nid, "password": "Whatever123!"},
        )
        assert r.status_code == 403
        assert r.json()["detail"] == "LEGACY_LOGIN_DISABLED"
    finally:
        config_module.settings.legacy_patient_password_login_enabled = True
        client._async_cleanup()  # type: ignore[attr-defined]


def test_password_register_disabled(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    nid = _national_id_from_seed("reg-disabled")
    try:
        r = client.post(
            "/api/auth/register",
            json={"national_id": nid, "password": "VeryStrongPassword123!"},
        )
        assert r.status_code == 410
        assert r.json()["detail"] == "REGISTER_DISABLED"
    finally:
        client._async_cleanup()  # type: ignore[attr-defined]


def test_console_sms_refuses_production(monkeypatch) -> None:
    import app.services.sms as sms_mod

    monkeypatch.setattr(sms_mod, "is_production_env", lambda: True)
    with pytest.raises(RuntimeError):
        sms_mod.ConsoleSmsProvider()
