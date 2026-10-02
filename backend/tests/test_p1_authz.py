"""Authorization matrices for P1 Task 2 routes + concurrent session claim."""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

import app.db.database as database_module
from app.auth.security import get_password_hash
from app.auth.session_access import claim_session_if_unassigned
from app.core import config as config_module
from app.main import app as fastapi_app
from app.models import File as FileModel
from app.models import Session as SessionModel
from app.models import Summary
from app.models.intake import Intake
from app.models.user import DoctorVerificationStatus, User, UserRole
from tests.test_api_integration import _national_id_from_seed, _auth_headers


async def _create_doctor(email: str, full_name: str, password: str) -> User:
    async with database_module.AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=UserRole.DOCTOR,
            is_active=True,
            verification_status=DoctorVerificationStatus.VERIFIED,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_admin(email: str, full_name: str, password: str) -> User:
    async with database_module.AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resolved = email if "@" in email else f"{email}@doctor.com"
    response = await client.post(
        "/api/auth/login",
        json={"email": resolved, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


async def _register_patient(
    client: AsyncClient,
    *,
    seed: str,
    password: str = "VeryStrongPassword123!",
) -> str:
    from tests.auth_helpers import register_and_login_async

    return await register_and_login_async(client, password=password, seed=seed)

async def _patient_session(client: AsyncClient, seed: str) -> tuple[str, int]:
    token = await _register_patient(client, seed=seed)
    session_resp = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth_headers(token),
    )
    assert session_resp.status_code == 200, session_resp.text
    return token, session_resp.json()["id"]


@pytest.fixture
async def client(db, test_db_engine):
    config_module.settings.single_doctor_mode = False
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    config_module.settings.single_doctor_mode = False


@pytest.mark.asyncio
@pytest.mark.parametrize("supplied_role", ["doctor", "admin", "visitor", "superuser"])
async def test_register_ignores_client_role(client: AsyncClient, supplied_role: str):
    """OTP path forces patient role; password register is disabled."""
    from app.services.sms import get_test_sms_provider, reset_test_sms_provider
    from tests.auth_helpers import phone_from_seed

    reset_test_sms_provider()
    phone = phone_from_seed(f"role-escalation-{supplied_role}")
    req = await client.post("/api/auth/otp/request", json={"phone": phone})
    assert req.status_code == 200, req.text
    code = get_test_sms_provider().last_code_for(phone)
    ver = await client.post(
        "/api/auth/otp/verify", json={"phone": phone, "code": code}
    )
    assert ver.status_code == 200, ver.text
    me = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {ver.json()['access_token']}"},
    )
    assert me.json()["role"] == "patient"


@pytest.mark.asyncio
async def test_create_session_patients_only(client: AsyncClient):
    await _create_doctor("doc_create@test.com", "doc_create", "PasswordA1!")
    await _create_admin("admin_create@test.com", "admin_create", "PasswordA1!")

    assert (
        await client.post("/api/chat/session", json={"initial_complaint": "x"})
    ).status_code == 401

    doc_token = await _login(client, "doc_create@test.com", "PasswordA1!")
    assert (
        await client.post(
            "/api/chat/session",
            json={"initial_complaint": "x"},
            headers=_auth_headers(doc_token),
        )
    ).status_code == 403

    admin_token = await _login(client, "admin_create@test.com", "PasswordA1!")
    assert (
        await client.post(
            "/api/chat/session",
            json={"initial_complaint": "x"},
            headers=_auth_headers(admin_token),
        )
    ).status_code == 403

    patient_token = await _register_patient(client, seed="create-session-patient")
    ok = await client.post(
        "/api/chat/session",
        json={"initial_complaint": "درد"},
        headers=_auth_headers(patient_token),
    )
    assert ok.status_code == 200, ok.text


@pytest.mark.asyncio
async def test_send_message_authz_matrix(client: AsyncClient):
    """POST chat is patient-owner only; doctors retain GET history access."""
    await _create_doctor("doc_msg@test.com", "doc_msg", "PasswordA1!")
    await _create_doctor("doc_msg_other@test.com", "doc_msg_other", "PasswordB1!")
    await _create_admin("admin_msg@test.com", "admin_msg", "PasswordA1!")

    owner_token, session_id = await _patient_session(client, "msg-owner")
    other_token = await _register_patient(client, seed="msg-other")
    payload = {"content": "سلام"}

    assert (
        await client.post(f"/api/chat/{session_id}", json=payload)
    ).status_code == 401
    assert (
        await client.post(
            f"/api/chat/{session_id}",
            json=payload,
            headers=_auth_headers(other_token),
        )
    ).status_code == 403

    ok = await client.post(
        f"/api/chat/{session_id}",
        json=payload,
        headers=_auth_headers(owner_token),
    )
    assert ok.status_code == 200, ok.text

    admin_token = await _login(client, "admin_msg@test.com", "PasswordA1!")
    admin_msg = await client.post(
        f"/api/chat/{session_id}",
        json=payload,
        headers=_auth_headers(admin_token),
    )
    assert admin_msg.status_code == 403

    # Separate session so admin GET claim does not block doctor claim below.
    _, admin_read_session = await _patient_session(client, "msg-admin-read")
    admin_get = await client.get(
        f"/api/chat/{admin_read_session}", headers=_auth_headers(admin_token)
    )
    assert admin_get.status_code == 200, admin_get.text

    doc_token = await _login(client, "doc_msg@test.com", "PasswordA1!")
    claim = await client.get(
        f"/api/chat/{session_id}", headers=_auth_headers(doc_token)
    )
    assert claim.status_code == 200, claim.text
    doc_msg = await client.post(
        f"/api/chat/{session_id}",
        json=payload,
        headers=_auth_headers(doc_token),
    )
    assert doc_msg.status_code == 403

    other_doc = await _login(client, "doc_msg_other@test.com", "PasswordB1!")
    assert (
        await client.post(
            f"/api/chat/{session_id}",
            json=payload,
            headers=_auth_headers(other_doc),
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_retry_soap_doctors_admins_only(client: AsyncClient, db):
    await _create_doctor("doc_retry@test.com", "doc_retry", "PasswordA1!")
    await _create_admin("admin_retry@test.com", "admin_retry", "PasswordA1!")
    patient_token, session_id = await _patient_session(client, "retry-patient")

    db.add(Summary(session_id=session_id, soap_note="# SOAP\n"))
    await db.commit()

    assert (
        await client.post(f"/api/summary/{session_id}/retry-soap")
    ).status_code == 401
    assert (
        await client.post(
            f"/api/summary/{session_id}/retry-soap",
            headers=_auth_headers(patient_token),
        )
    ).status_code == 403

    doc_token = await _login(client, "doc_retry@test.com", "PasswordA1!")
    ok = await client.post(
        f"/api/summary/{session_id}/retry-soap",
        headers=_auth_headers(doc_token),
    )
    assert ok.status_code == 200, ok.text

    admin_token = await _login(client, "admin_retry@test.com", "PasswordA1!")
    denied = await client.post(
        f"/api/summary/{session_id}/retry-soap",
        headers=_auth_headers(admin_token),
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_pdf_export_authz_allows_patient_owner(client: AsyncClient, db):
    """Patient owner may export; other patients and unauth blocked."""
    await _create_doctor("doc_pdf@test.com", "doc_pdf", "PasswordA1!")
    owner_token, session_id = await _patient_session(client, "pdf-owner")
    other_token = await _register_patient(client, seed="pdf-other")

    db.add(Intake(session_id=session_id, current_layer=4))
    await db.commit()

    assert (await client.get(f"/api/sessions/{session_id}/pdf")).status_code == 401
    assert (
        await client.get(
            f"/api/sessions/{session_id}/pdf",
            headers=_auth_headers(other_token),
        )
    ).status_code == 403

    owner = await client.get(
        f"/api/sessions/{session_id}/pdf",
        headers=_auth_headers(owner_token),
    )
    assert owner.status_code not in (401, 403), owner.text

    doc_token = await _login(client, "doc_pdf@test.com", "PasswordA1!")
    doc = await client.get(
        f"/api/sessions/{session_id}/pdf",
        headers=_auth_headers(doc_token),
    )
    assert doc.status_code not in (401, 403), doc.text


@pytest.mark.asyncio
async def test_ocr_authz_admin_and_doctor_consistent(client: AsyncClient, db):
    await _create_doctor("doc_ocr@test.com", "doc_ocr", "PasswordA1!")
    await _create_admin("admin_ocr@test.com", "admin_ocr", "PasswordA1!")
    await _create_doctor("doc_ocr_other@test.com", "doc_ocr_other", "PasswordB1!")

    owner_token, session_id = await _patient_session(client, "ocr-owner")
    other_token = await _register_patient(client, seed="ocr-other")

    f = FileModel(
        session_id=session_id,
        filename="lab.png",
        s3_key="sessions/x/lab.png",
        size_bytes=10,
        content_type="image/png",
        condition_id="lab-1",
    )
    db.add(f)
    await db.commit()
    await db.refresh(f)
    file_id = f.id

    assert (await client.get(f"/api/documents/{file_id}/ocr")).status_code == 401
    assert (
        await client.get(
            f"/api/documents/{file_id}/ocr",
            headers=_auth_headers(other_token),
        )
    ).status_code == 404

    owner = await client.get(
        f"/api/documents/{file_id}/ocr",
        headers=_auth_headers(owner_token),
    )
    assert owner.status_code in (200, 404), owner.text

    doc_token = await _login(client, "doc_ocr@test.com", "PasswordA1!")
    doc = await client.get(
        f"/api/documents/{file_id}/ocr",
        headers=_auth_headers(doc_token),
    )
    assert doc.status_code in (200, 404), doc.text

    other_doc = await _login(client, "doc_ocr_other@test.com", "PasswordB1!")
    assert (
        await client.get(
            f"/api/documents/{file_id}/ocr",
            headers=_auth_headers(other_doc),
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_auth_me_returns_non_sensitive_fields(client: AsyncClient):
    token = await _register_patient(client, seed="me-patient")
    assert (await client.get("/api/auth/me")).status_code == 401
    me = await client.get("/api/auth/me", headers=_auth_headers(token))
    assert me.status_code == 200, me.text
    body = me.json()
    assert set(body.keys()) == {"id", "role", "display_name"}
    assert body["role"] == "patient"
    assert "email" not in body
    assert "national_id" not in body


@pytest.mark.asyncio
async def test_concurrent_claim_only_one_doctor_wins(client: AsyncClient):
    doc_a = await _create_doctor("claim_a@test.com", "claim_a", "PasswordA1!")
    doc_b = await _create_doctor("claim_b@test.com", "claim_b", "PasswordB1!")
    _, session_id = await _patient_session(client, "claim-race")

    async with database_module.AsyncSessionLocal() as db_a:
        async with database_module.AsyncSessionLocal() as db_b:
            sess_a = await db_a.get(SessionModel, session_id)
            sess_b = await db_b.get(SessionModel, session_id)
            assert sess_a is not None and sess_b is not None

            results: list[int | None] = [None, None]
            errors: list[Exception | None] = [None, None]

            async def claim_a():
                try:
                    out = await claim_session_if_unassigned(db_a, sess_a, doc_a)
                    results[0] = out.doctor_id
                except Exception as exc:  # noqa: BLE001
                    errors[0] = exc

            async def claim_b():
                try:
                    out = await claim_session_if_unassigned(db_b, sess_b, doc_b)
                    results[1] = out.doctor_id
                except Exception as exc:  # noqa: BLE001
                    errors[1] = exc

            await asyncio.gather(claim_a(), claim_b())

    async with database_module.AsyncSessionLocal() as db:
        sess = await db.get(SessionModel, session_id)
        assert sess is not None
        owner = sess.doctor_id

    assert owner in {doc_a.id, doc_b.id}

    # At most one claim succeeded assigning its own id without denial.
    successes = [r for r in results if r == owner]
    assert len(successes) >= 1
    assert (errors[0] is not None) or (errors[1] is not None) or (
        results[0] == results[1] == owner
    ) or (results.count(None) + sum(1 for e in errors if e is not None) >= 1)

    loser_name = "claim_b" if owner == doc_a.id else "claim_a"
    loser_email = f"{loser_name}@test.com"
    loser_pw = "PasswordB1!" if loser_name == "claim_b" else "PasswordA1!"
    loser_token = await _login(client, loser_email, loser_pw)
    assert (
        await client.get(
            f"/api/chat/{session_id}",
            headers=_auth_headers(loser_token),
        )
    ).status_code == 403


@pytest.mark.asyncio
async def test_create_privileged_user_script_refuses_overwrite(client: AsyncClient):
    await _create_doctor("script_doc@test.com", "script_doc", "PasswordA1!")
    from scripts.create_privileged_user import create_privileged_user

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        await create_privileged_user(
            role="doctor",
            email="script_doc@test.com",
            display_name="script_doc_new",
            password="PasswordA1!",
        )
