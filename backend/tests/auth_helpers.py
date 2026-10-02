"""Shared auth helpers for tests after P2-B OTP identity."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.security import get_password_hash
from app.db.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.sms import get_test_sms_provider, reset_test_sms_provider
from app.utils.national_id import validate_iranian_national_id
from app.utils.phone import normalize_iranian_mobile


def national_id_from_seed(seed: str) -> str:
    candidate = 1_000_000_000 + (abs(hash(seed)) % 900_000_000)
    while candidate < 9_999_999_999:
        national_id = str(candidate).zfill(10)
        if validate_iranian_national_id(national_id):
            return national_id
        candidate += 1
    return "0499370899"


def phone_from_seed(seed: str) -> str:
    """Synthetic Iranian mobile in E.164 (fake; never a real subscriber)."""
    # Use 91… prefix so the local form never starts with ``98`` (which
    # normalize would misread as a country-code prefix).
    n = abs(hash(seed)) % 100_000_000
    local = f"91{n:08d}"
    phone = normalize_iranian_mobile(local)
    assert phone is not None, f"failed to normalize synthetic local={local!r}"
    return phone


async def create_legacy_patient_async(
    *,
    national_id: str,
    password: str = "VeryStrongPassword123!",
    phone: str | None = None,
    full_name: str | None = None,
) -> int:
    import app.db.database as database_module

    async with database_module.AsyncSessionLocal() as db:
        user = User(
            email=f"patient_{national_id}@patient.local",
            full_name=full_name or f"بیمار {national_id[-4:]}",
            national_id=national_id,
            phone=phone,
            hashed_password=get_password_hash(password),
            role=UserRole.PATIENT,
            is_active=True,
        )
        db.add(user)
        await db.flush()
        from app.services.platform_identity_service import ensure_patient_profile

        await ensure_patient_profile(db, user)
        await db.commit()
        await db.refresh(user)
        return int(user.id)


def create_legacy_patient(
    *,
    national_id: str,
    password: str = "VeryStrongPassword123!",
    phone: str | None = None,
    full_name: str | None = None,
) -> int:
    """Insert a password-backed patient (legacy path) and return user id."""
    return asyncio.run(
        create_legacy_patient_async(
            national_id=national_id,
            password=password,
            phone=phone,
            full_name=full_name,
        )
    )


def register_and_login(
    client: TestClient,
    *,
    national_id: str | None = None,
    password: str = "VeryStrongPassword123!",
    seed: str = "default-patient",
) -> str:
    """Create a legacy patient (DB) and login via national_id + password.

    Password self-register is disabled; tests use this helper instead.
    Patients get a phone so login issues tokens without PHONE_LINK_REQUIRED.
    """
    resolved = national_id or national_id_from_seed(seed)
    phone = phone_from_seed(seed)
    create_legacy_patient(
        national_id=resolved, password=password, phone=phone
    )
    login_response = client.post(
        "/api/auth/login",
        json={"national_id": resolved, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    body = login_response.json()
    assert body.get("access_token")
    return body["access_token"]


def register_and_login_with_id(
    client: TestClient,
    *,
    national_id: str | None = None,
    password: str = "VeryStrongPassword123!",
    seed: str = "default-patient",
) -> tuple[str, int]:
    resolved = national_id or national_id_from_seed(seed)
    phone = phone_from_seed(seed)
    user_id = create_legacy_patient(
        national_id=resolved, password=password, phone=phone
    )
    login_response = client.post(
        "/api/auth/login",
        json={"national_id": resolved, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["access_token"], user_id


async def register_and_login_async(
    client,
    *,
    national_id: str | None = None,
    password: str = "VeryStrongPassword123!",
    seed: str = "default-patient",
) -> str:
    resolved = national_id or national_id_from_seed(seed)
    phone = phone_from_seed(seed)
    await create_legacy_patient_async(
        national_id=resolved, password=password, phone=phone
    )
    login = await client.post(
        "/api/auth/login",
        json={"national_id": resolved, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


async def register_and_login_with_id_async(
    client,
    *,
    national_id: str | None = None,
    password: str = "VeryStrongPassword123!",
    seed: str = "default-patient",
) -> tuple[str, int]:
    resolved = national_id or national_id_from_seed(seed)
    phone = phone_from_seed(seed)
    user_id = await create_legacy_patient_async(
        national_id=resolved, password=password, phone=phone
    )
    login = await client.post(
        "/api/auth/login",
        json={"national_id": resolved, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], user_id


def otp_register_and_login(
    client: TestClient,
    *,
    phone: str | None = None,
    seed: str = "otp-patient",
) -> tuple[str, str]:
    """OTP create/login via TestSmsProvider. Returns (access_token, e164_phone)."""
    reset_test_sms_provider()
    resolved = phone or phone_from_seed(seed)
    req = client.post("/api/auth/otp/request", json={"phone": resolved})
    assert req.status_code == 200, req.text
    code = get_test_sms_provider().last_code_for(resolved)
    assert code
    ver = client.post(
        "/api/auth/otp/verify",
        json={"phone": resolved, "code": code},
    )
    assert ver.status_code == 200, ver.text
    return ver.json()["access_token"], resolved


def doctor_login(
    client: TestClient,
    *,
    username: str,
    password: str,
) -> str:
    """Login privileged user by email ``{username}@doctor.com``."""
    email = username if "@" in username else f"{username}@doctor.com"
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def find_user_by_national_id(national_id: str) -> User | None:
    import app.db.database as database_module

    async with database_module.AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.national_id == national_id))
        return result.scalar_one_or_none()
