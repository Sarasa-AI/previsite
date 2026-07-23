"""RBAC: doctor A must not access doctor B's assigned sessions."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.db.database as database_module
from app.auth.security import get_password_hash
from app.core import config as config_module
from app.main import app as fastapi_app
from app.models import Session as SessionModel
from app.models import Summary
from app.models.user import User, UserRole
from tests.conftest import setup_async_test_db, teardown_test_db
from tests.test_mvp_flow import _register_and_login


def _create_client(tmp_path, monkeypatch):
    engine = asyncio.run(setup_async_test_db(tmp_path, monkeypatch))
    client = TestClient(fastapi_app)

    def cleanup():
        teardown_test_db()
        asyncio.run(engine.dispose())
        client.close()

    client._async_cleanup = cleanup  # type: ignore[attr-defined]
    return client


async def _create_doctor(email: str, full_name: str, password: str) -> User:
    async with database_module.AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=UserRole.DOCTOR,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"national_id": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_doctor_b_cannot_access_session_assigned_to_doctor_a(tmp_path, monkeypatch) -> None:
    config_module.settings.single_doctor_mode = False
    client = _create_client(tmp_path, monkeypatch)

    asyncio.run(_create_doctor("doctor_a@test.com", "doctor_a", "PasswordA1!"))
    asyncio.run(_create_doctor("doctor_b@test.com", "doctor_b", "PasswordB1!"))

    patient_token = _register_and_login(client, seed="rbac-patient-1")
    session_resp = client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth(patient_token),
    )
    assert session_resp.status_code == 200, session_resp.text
    session_id = session_resp.json()["id"]

    async def _add_summary() -> None:
        async with database_module.AsyncSessionLocal() as db:
            db.add(Summary(session_id=session_id, soap_note="# SOAP\n"))
            await db.commit()

    asyncio.run(_add_summary())

    token_a = _login(client, "doctor_a", "PasswordA1!")
    claim = client.get(f"/api/summary/{session_id}", headers=_auth(token_a))
    assert claim.status_code == 200, claim.text

    async def _assert_assigned() -> None:
        async with database_module.AsyncSessionLocal() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = result.scalar_one()
            assert session.doctor_id is not None

    asyncio.run(_assert_assigned())

    token_b = _login(client, "doctor_b", "PasswordB1!")
    headers_b = _auth(token_b)

    assert client.get(f"/api/chat/{session_id}", headers=headers_b).status_code == 403
    assert client.get(f"/api/summary/{session_id}", headers=headers_b).status_code == 403
    assert (
        client.get(f"/api/sessions/{session_id}/pdf", headers=headers_b).status_code
        == 403
    )

    list_b = client.get("/api/chat/sessions", headers=headers_b)
    assert list_b.status_code == 200
    ids = {s["id"] for s in list_b.json()}
    assert session_id not in ids

    client._async_cleanup()


def test_unassigned_session_claim_then_blocks_other_doctor(tmp_path, monkeypatch) -> None:
    config_module.settings.single_doctor_mode = False
    client = _create_client(tmp_path, monkeypatch)

    asyncio.run(_create_doctor("doc1@test.com", "doc1", "PasswordA1!"))
    asyncio.run(_create_doctor("doc2@test.com", "doc2", "PasswordB1!"))

    patient_token = _register_and_login(client, seed="rbac-patient-2")
    session_id = client.post(
        "/api/chat/session",
        json={"initial_complaint": "درد"},
        headers=_auth(patient_token),
    ).json()["id"]

    token_1 = _login(client, "doc1", "PasswordA1!")
    token_2 = _login(client, "doc2", "PasswordB1!")

    list_2 = client.get("/api/chat/sessions", headers=_auth(token_2))
    assert session_id in {s["id"] for s in list_2.json()}

    assert (
        client.get(f"/api/chat/{session_id}", headers=_auth(token_1)).status_code == 200
    )
    assert (
        client.get(f"/api/chat/{session_id}", headers=_auth(token_2)).status_code == 403
    )

    client._async_cleanup()


def test_single_doctor_mode_allows_cross_access(tmp_path, monkeypatch) -> None:
    config_module.settings.single_doctor_mode = True
    client = _create_client(tmp_path, monkeypatch)

    asyncio.run(_create_doctor("solo_a@test.com", "solo_a", "PasswordA1!"))
    asyncio.run(_create_doctor("solo_b@test.com", "solo_b", "PasswordB1!"))

    patient_token = _register_and_login(client, seed="rbac-patient-3")
    session_id = client.post(
        "/api/chat/session",
        json={"initial_complaint": "تب"},
        headers=_auth(patient_token),
    ).json()["id"]

    async def _assign_to_a() -> None:
        async with database_module.AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.full_name == "solo_a"))
            doctor_a = result.scalar_one()
            sess = await db.get(SessionModel, session_id)
            assert sess is not None
            sess.doctor_id = doctor_a.id
            await db.commit()

    asyncio.run(_assign_to_a())

    token_b = _login(client, "solo_b", "PasswordB1!")
    assert (
        client.get(f"/api/chat/{session_id}", headers=_auth(token_b)).status_code == 200
    )

    config_module.settings.single_doctor_mode = False
    client._async_cleanup()
