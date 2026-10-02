from tests.auth_helpers import register_and_login_async, register_and_login_with_id_async, national_id_from_seed
"""P1 tests: field encryption, migration health, rate limits, audit events."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.core.rate_limiter import rate_limiter
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.security.field_crypto import (
    FieldCryptoError,
    decrypt_field,
    encrypt_field,
    is_encrypted,
    validate_fernet_key,
)
from app.services.audit_service import (
    AUDIT_INTAKE_READ,
    AUDIT_SESSION_ACCESS_DENIED,
    record_audit,
)
from tests.test_api_integration import _auth_headers, _national_id_from_seed


@pytest.fixture
def fernet_key() -> str:
    return Fernet.generate_key().decode()


def test_field_crypto_round_trip(fernet_key: str) -> None:
    cipher = encrypt_field("secret-value", fernet_key)
    assert is_encrypted(cipher)
    assert cipher.startswith("v1:")
    assert decrypt_field(cipher, fernet_key) == "secret-value"


def test_field_crypto_legacy_plaintext(fernet_key: str) -> None:
    assert decrypt_field("legacy-plain", fernet_key) == "legacy-plain"
    assert not is_encrypted("legacy-plain")


def test_field_crypto_wrong_key(fernet_key: str) -> None:
    cipher = encrypt_field("secret-value", fernet_key)
    other = Fernet.generate_key().decode()
    with pytest.raises(FieldCryptoError):
        decrypt_field(cipher, other)


def test_validate_fernet_key(fernet_key: str) -> None:
    assert validate_fernet_key(fernet_key) is True
    assert validate_fernet_key("") is False
    assert validate_fernet_key("not-a-key") is False


def test_startup_requires_field_key_when_mfa_production(monkeypatch) -> None:
    monkeypatch.setattr(config_module.settings, "secret_key", "a" * 32)
    monkeypatch.setattr(config_module.settings, "app_env", "production")
    monkeypatch.setattr(config_module.settings, "mfa_enabled", True)
    monkeypatch.setattr(config_module.settings, "field_encryption_key", None)
    monkeypatch.setattr(config_module.settings, "db_password", "strong-db-pass")
    monkeypatch.setattr(config_module.settings, "s3_access_key", "prod-access")
    monkeypatch.setattr(config_module.settings, "s3_secret_key", "prod-secret")
    monkeypatch.setattr(config_module.settings, "seed_doctor_password", "seed-pass")
    with pytest.raises(SystemExit, match="FIELD_ENCRYPTION_KEY"):
        config_module.validate_startup_config()


@pytest.mark.asyncio
async def test_check_migrations_ok_behind_unknown(db, monkeypatch):
    from app.core.health_checks import check_migrations

    # unknown when alembic_version missing / empty on SQLite test DB
    status = await check_migrations(db)
    assert status["status"] in {"ok", "behind", "unknown"}

    async def boom(_db):
        raise RuntimeError("fail")

    # Non-fatal: force unknown via broken ScriptDirectory
    monkeypatch.setattr(
        "alembic.script.ScriptDirectory.from_config",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("x")),
    )
    status2 = await check_migrations(db)
    assert status2["status"] == "unknown"


@pytest.mark.asyncio
async def test_detailed_health_includes_migrations(db, test_db_engine):
    admin = User(
        email="mig-health@test.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="mig_health",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    token = create_access_token(data={"sub": str(admin.id), "email": admin.email})

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health/detailed",
            headers=_auth_headers(token),
        )
    assert response.status_code == 200
    body = response.json()
    assert "migrations" in body["dependencies"]
    assert body["dependencies"]["migrations"]["status"] in {
        "ok",
        "behind",
        "unknown",
    }


@pytest.mark.asyncio
async def test_medications_search_rate_limit(db, test_db_engine, monkeypatch):
    rate_limiter.reset()
    monkeypatch.setattr(
        config_module.settings, "medications_search_rate_limit_requests", 2
    )
    monkeypatch.setattr(
        config_module.settings, "medications_search_rate_limit_window_seconds", 60
    )

    national_id = _national_id_from_seed("rate-med-search")
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        token = await register_and_login_async(
            client, national_id=national_id, password="VeryStrongPassword123!", seed=str(national_id)
        )
        headers = _auth_headers(token)

        # Normal use under limit
        r1 = await client.get("/api/medications/search?query=met", headers=headers)
        r2 = await client.get("/api/medications/search?query=met", headers=headers)
        assert r1.status_code != 429
        assert r2.status_code != 429

        r3 = await client.get("/api/medications/search?query=met", headers=headers)
        assert r3.status_code == 429

    rate_limiter.reset()
    monkeypatch.setattr(
        config_module.settings, "medications_search_rate_limit_requests", 60
    )


@pytest.mark.asyncio
async def test_audit_intake_read_and_session_denied(db, test_db_engine):
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        nid = _national_id_from_seed("audit-intake-owner")
        owner_token = await register_and_login_async(
            client, national_id=nid, password="VeryStrongPassword123!", seed=str(nid)
        )

        session = await client.post(
            "/api/chat/session",
            json={"initial_complaint": "درد"},
            headers=_auth_headers(owner_token),
        )
        session_id = session.json()["id"]

        read = await client.get(
            f"/api/intake/{session_id}",
            headers=_auth_headers(owner_token),
        )
        assert read.status_code == 200, read.text

        nid2 = _national_id_from_seed("audit-intake-other")
        other_token = await register_and_login_async(
            client, national_id=nid2, password="VeryStrongPassword123!", seed=str(nid2)
        )
        denied = await client.get(
            f"/api/intake/{session_id}",
            headers=_auth_headers(other_token),
        )
        assert denied.status_code == 403

    reads = (
        await db.execute(select(AuditLog).where(AuditLog.action == AUDIT_INTAKE_READ))
    ).scalars().all()
    assert len(reads) >= 1
    row = reads[-1]
    assert row.resource_type == "session"
    assert row.resource_id == str(session_id)
    assert row.previous_value is None
    # No clinical free text in audited fields
    for field in (row.action, row.resource_type, row.resource_id, row.ip_address):
        if field:
            assert "درد" not in str(field)

    denials = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_SESSION_ACCESS_DENIED)
        )
    ).scalars().all()
    assert len(denials) >= 1


@pytest.mark.asyncio
async def test_audit_pdf_export_and_file_list(db, test_db_engine):
    from app.models.intake import Intake
    from app.services.audit_service import AUDIT_FILE_LIST, AUDIT_PDF_EXPORT

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        nid = _national_id_from_seed("audit-pdf-owner")
        token = await register_and_login_async(
            client, national_id=nid, password="VeryStrongPassword123!", seed=str(nid)
        )
        headers = _auth_headers(token)
        session = await client.post(
            "/api/chat/session",
            json={"initial_complaint": "سرفه"},
            headers=headers,
        )
        session_id = session.json()["id"]

        db.add(Intake(session_id=session_id, current_layer=4))
        await db.commit()

        listed = await client.get(f"/api/files/{session_id}/list", headers=headers)
        assert listed.status_code == 200, listed.text

        pdf = await client.get(f"/api/sessions/{session_id}/pdf", headers=headers)
        assert pdf.status_code not in (401, 403), pdf.text

    lists = (
        await db.execute(select(AuditLog).where(AuditLog.action == AUDIT_FILE_LIST))
    ).scalars().all()
    assert any(r.resource_id == str(session_id) for r in lists)
    for r in lists:
        assert r.previous_value is None
        assert "سرفه" not in (r.action or "")

    exports = (
        await db.execute(select(AuditLog).where(AuditLog.action == AUDIT_PDF_EXPORT))
    ).scalars().all()
    assert any(r.resource_id == str(session_id) for r in exports)


@pytest.mark.asyncio
async def test_audit_pmh_overview_other_reader(db, test_db_engine):
    from app.auth.security import get_password_hash as _hash
    from app.models.user import User, UserRole
    from app.services.audit_service import (
        AUDIT_PMH_OVERVIEW_READ,
        AUDIT_PROFILE_READ_OTHER,
    )

    doctor = User(
        email="audit_pmh_doc@test.com",
        full_name="audit_pmh_doc",
        hashed_password=_hash("PasswordA1!"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        nid = _national_id_from_seed("audit-pmh-patient")
        patient_token = await register_and_login_async(
            client, national_id=nid, password="VeryStrongPassword123!", seed=str(nid)
        )
        me = await client.get("/api/auth/me", headers=_auth_headers(patient_token))
        patient_id = me.json()["id"]

        # Create an unassigned session so doctor_may_access_patient is true
        await client.post(
            "/api/chat/session",
            json={"initial_complaint": "درد"},
            headers=_auth_headers(patient_token),
        )

        doc_login = await client.post(
            "/api/auth/login",
            json={"email": "audit_pmh_doc@doctor.com", "password": "PasswordA1!"},
        )
        doc_token = doc_login.json()["access_token"]
        overview = await client.get(
            f"/api/pmh/overview/{patient_id}",
            headers=_auth_headers(doc_token),
        )
        assert overview.status_code == 200, overview.text

    reads = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_PMH_OVERVIEW_READ)
        )
    ).scalars().all()
    assert any(r.resource_id == str(patient_id) for r in reads)

    others = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == AUDIT_PROFILE_READ_OTHER)
        )
    ).scalars().all()
    assert any(r.resource_id == str(patient_id) for r in others)
    for r in others:
        assert "درد" not in str(r.resource_id)
        assert r.previous_value is None


@pytest.mark.asyncio
async def test_record_audit_fail_soft(db):
    await record_audit(
        db,
        action="test_action",
        user_id=None,
        resource_type="session",
        resource_id=1,
        ip_address="127.0.0.1",
    )
    rows = (
        await db.execute(select(AuditLog).where(AuditLog.action == "test_action"))
    ).scalars().all()
    assert len(rows) == 1
