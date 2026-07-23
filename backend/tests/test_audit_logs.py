"""Tests for minimal audit trail API."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

import app.db.database as database_module
from app.auth.security import get_password_hash
from app.main import app as fastapi_app
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


async def _create_admin(password: str = "AdminPass123!") -> None:
    async with database_module.AsyncSessionLocal() as db:
        db.add(
            User(
                email="audit_admin@test.com",
                full_name="audit_admin",
                hashed_password=get_password_hash(password),
                role=UserRole.ADMIN,
                is_active=True,
            )
        )
        await db.commit()


def test_login_writes_audit_log_and_admin_can_list(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    asyncio.run(_create_admin())

    token = _register_and_login(client, seed="audit-patient")
    assert token

    admin_login = client.post(
        "/api/auth/login",
        json={"national_id": "audit_admin", "password": "AdminPass123!"},
    )
    assert admin_login.status_code == 200, admin_login.text
    admin_headers = {
        "Authorization": f"Bearer {admin_login.json()['access_token']}"
    }

    logs = client.get("/api/admin/audit-logs", headers=admin_headers)
    assert logs.status_code == 200, logs.text
    actions = [row["action"] for row in logs.json()]
    assert "login" in actions

    # Non-admin forbidden
    patient_headers = {"Authorization": f"Bearer {token}"}
    denied = client.get("/api/admin/audit-logs", headers=patient_headers)
    assert denied.status_code == 403

    client._async_cleanup()
