"""GET /metrics access matrix (admin JWT or METRICS_BEARER_TOKEN)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

import app.db.database as database_module
from app.auth.security import create_access_token, get_password_hash
from app.core import config as config_module
from app.main import app
from app.models.user import User, UserRole


async def _create_user(*, email: str, full_name: str, role: UserRole, password: str) -> User:
    async with database_module.AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=get_password_hash(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest.fixture
async def client(db, test_db_engine):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_metrics_anonymous_denied(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config_module.settings, "metrics_bearer_token", None)
    monkeypatch.setattr(config_module.settings, "app_env", "test")
    response = await client.get("/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_anonymous_404_in_production_without_token(
    client: AsyncClient, monkeypatch
):
    monkeypatch.setattr(config_module.settings, "metrics_bearer_token", None)
    monkeypatch.setattr(config_module.settings, "app_env", "production")
    response = await client.get("/metrics")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_metrics_bearer_token_allowed(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config_module.settings, "metrics_bearer_token", "metrics-secret-ci")
    monkeypatch.setattr(config_module.settings, "app_env", "test")
    response = await client.get(
        "/metrics",
        headers={"Authorization": "Bearer metrics-secret-ci"},
    )
    assert response.status_code == 200
    assert "previsit_soap_success_total" in response.text


@pytest.mark.asyncio
async def test_metrics_admin_jwt_allowed(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config_module.settings, "metrics_bearer_token", None)
    monkeypatch.setattr(config_module.settings, "app_env", "test")
    admin = await _create_user(
        email="metrics_admin@test.com",
        full_name="metrics_admin",
        role=UserRole.ADMIN,
        password="PasswordA1!",
    )
    token = create_access_token({"sub": str(admin.id), "email": admin.email})
    response = await client.get(
        "/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_metrics_non_admin_jwt_forbidden(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(config_module.settings, "metrics_bearer_token", None)
    monkeypatch.setattr(config_module.settings, "app_env", "test")
    doctor = await _create_user(
        email="metrics_doc@test.com",
        full_name="metrics_doc",
        role=UserRole.DOCTOR,
        password="PasswordA1!",
    )
    token = create_access_token({"sub": str(doctor.id), "email": doctor.email})
    response = await client.get(
        "/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
