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

    from tests.auth_helpers import national_id_from_seed

    national_id = national_id_from_seed("lockout-patient")

    for i in range(settings.auth_login_max_failures):
        resp = client.post(
            "/api/auth/login",
            json={"national_id": national_id, "password": "wrong-password"},
        )
        assert resp.status_code in (401, 429), (i, resp.status_code, resp.text)

    locked = client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": password},
    )
    assert locked.status_code == 429, locked.text
    assert "locked" in locked.json()["detail"].lower()

    client._async_cleanup()


def test_register_rate_limit_by_ip(tmp_path, monkeypatch) -> None:
    """OTP request is rate-limited per IP (password register is disabled)."""
    client = _create_client(tmp_path, monkeypatch)
    from app.core import config as config_module
    from app.services.sms import reset_test_sms_provider
    from tests.auth_helpers import phone_from_seed

    original = settings.otp_request_per_ip_limit
    config_module.settings.otp_request_per_ip_limit = 3
    settings.otp_request_per_ip_limit = 3
    rate_limiter.reset()
    reset_test_sms_provider()

    try:
        statuses = []
        for i in range(5):
            phone = phone_from_seed(f"reg-limit-{i}")
            resp = client.post(
                "/api/auth/otp/request",
                json={"phone": phone},
            )
            statuses.append(resp.status_code)
        assert 429 in statuses
    finally:
        config_module.settings.otp_request_per_ip_limit = original
        settings.otp_request_per_ip_limit = original
        rate_limiter.reset()
        client._async_cleanup()
