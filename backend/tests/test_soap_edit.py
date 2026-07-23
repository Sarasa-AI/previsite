"""Tests for PATCH /api/sessions/{id}/soap free-text edit + RBAC."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

import app.db.database as database_module
from app.auth.security import get_password_hash
from app.core import config as config_module
from app.main import app as fastapi_app
from app.models import Summary
from app.models.audit_log import AuditLog
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


def test_unrelated_doctor_cannot_edit_soap(tmp_path, monkeypatch) -> None:
    config_module.settings.single_doctor_mode = False
    client = _create_client(tmp_path, monkeypatch)

    asyncio.run(_create_doctor("soap_a@test.com", "soap_a", "PasswordA1!"))
    asyncio.run(_create_doctor("soap_b@test.com", "soap_b", "PasswordB1!"))

    patient_token = _register_and_login(client, seed="soap-edit-patient")
    session_id = client.post(
        "/api/chat/session",
        json={"initial_complaint": "سردرد"},
        headers=_auth(patient_token),
    ).json()["id"]

    async def _seed_summary() -> None:
        async with database_module.AsyncSessionLocal() as db:
            db.add(Summary(session_id=session_id, soap_note="ORIGINAL SOAP"))
            await db.commit()

    asyncio.run(_seed_summary())

    token_a = _login(client, "soap_a", "PasswordA1!")
    ok = client.patch(
        f"/api/sessions/{session_id}/soap",
        json={"soap_note": "UPDATED BY A"},
        headers=_auth(token_a),
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["soap_note"] == "UPDATED BY A"

    token_b = _login(client, "soap_b", "PasswordB1!")
    denied = client.patch(
        f"/api/sessions/{session_id}/soap",
        json={"soap_note": "HIJACKED BY B"},
        headers=_auth(token_b),
    )
    assert denied.status_code == 403

    async def _assert_unchanged_and_audited() -> None:
        async with database_module.AsyncSessionLocal() as db:
            summary = (
                await db.execute(select(Summary).where(Summary.session_id == session_id))
            ).scalar_one()
            assert summary.soap_note == "UPDATED BY A"

            audits = (
                await db.execute(
                    select(AuditLog).where(AuditLog.action == "edit_soap")
                )
            ).scalars().all()
            assert any(a.previous_value == "ORIGINAL SOAP" for a in audits)

    asyncio.run(_assert_unchanged_and_audited())
    config_module.settings.single_doctor_mode = False
    client._async_cleanup()


def test_patient_cannot_edit_soap(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    patient_token = _register_and_login(client, seed="soap-edit-patient-2")
    session_id = client.post(
        "/api/chat/session",
        json={"initial_complaint": "درد"},
        headers=_auth(patient_token),
    ).json()["id"]

    async def _seed_summary() -> None:
        async with database_module.AsyncSessionLocal() as db:
            db.add(Summary(session_id=session_id, soap_note="PATIENT SOAP"))
            await db.commit()

    asyncio.run(_seed_summary())

    denied = client.patch(
        f"/api/sessions/{session_id}/soap",
        json={"soap_note": "patient rewrite"},
        headers=_auth(patient_token),
    )
    assert denied.status_code == 403
    client._async_cleanup()
