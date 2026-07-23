"""Auth brute-force lockout tests."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.rate_limiter import rate_limiter
from app.main import app as fastapi_app
from tests.conftest import setup_async_test_db, teardown_test_db
from tests.test_mvp_flow import _register_and_login


def _create_client(tmp_path, monkeypatch):
    engine = asyncio.run(setup_async_test_db(tmp_path, monkeypatch))
    client = TestClient(fastapi_app)
    rate_limiter.reset()

    def cleanup():
        teardown_test_db()
        rate_limiter.reset()
        asyncio.run(engine.dispose())
        client.close()

    client._async_cleanup = cleanup  # type: ignore[attr-defined]
    return client


def test_login_lockout_after_five_failures_blocks_even_correct_password(
    tmp_path, monkeypatch
) -> None:
    client = _create_client(tmp_path, monkeypatch)
    password = "VeryStrongPassword123!"
    token = _register_and_login(client, seed="lockout-patient", password=password)
    assert token

    # Resolve national_id the same way register does
    from tests.test_mvp_flow import _national_id_from_seed

    national_id = _national_id_from_seed("lockout-patient")

    for i in range(settings.auth_login_max_failures):
        resp = client.post(
            "/api/auth/login",
            json={"national_id": national_id, "password": "wrong-password"},
        )
        # First failures are 401; the 5th may already flip to 429 when lockout trips
        assert resp.status_code in (401, 429), (i, resp.status_code, resp.text)

    # Sixth attempt with the correct password must still be locked out
    locked = client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": password},
    )
    assert locked.status_code == 429, locked.text
    assert "locked" in locked.json()["detail"].lower()

    client._async_cleanup()


def test_register_rate_limit_by_ip(tmp_path, monkeypatch) -> None:
    client = _create_client(tmp_path, monkeypatch)
    from tests.test_mvp_flow import _national_id_from_seed

    # Temporarily tighten register limit for this test
    original = settings.auth_register_max_requests
    settings.auth_register_max_requests = 3
    rate_limiter.reset()

    try:
        statuses = []
        for i in range(5):
            nid = _national_id_from_seed(f"reg-limit-{i}")
            resp = client.post(
                "/api/auth/register",
                json={
                    "national_id": nid,
                    "password": "VeryStrongPassword123!",
                    "role": "patient",
                },
            )
            statuses.append(resp.status_code)
        assert 429 in statuses
    finally:
        settings.auth_register_max_requests = original
        rate_limiter.reset()
        client._async_cleanup()
