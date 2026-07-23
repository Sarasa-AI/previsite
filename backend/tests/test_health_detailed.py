"""Tests for public and admin detailed health endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_password_hash
from app.models.user import User, UserRole


@pytest.mark.asyncio
async def test_public_health_is_simple(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_detailed_health_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.get("/health/detailed")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_detailed_health_as_admin(async_client: AsyncClient, db: AsyncSession) -> None:
    admin = User(
        email="health-admin@example.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="health_admin",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)

    token = create_access_token(data={"sub": str(admin.id), "email": admin.email})
    response = await async_client.get(
        "/health/detailed",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "dependencies" in body
    assert "database" in body["dependencies"]
    assert "ollama" in body["dependencies"]
    assert "llm_provider" in body["dependencies"]
    assert body["dependencies"]["database"]["status"] == "ok"
