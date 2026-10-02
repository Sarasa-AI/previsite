"""Refresh-token rotation, reuse detection, revocation, and expiry."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_password_hash
from app.core import config as config_module
from app.models.audit_log import AuditLog
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services import refresh_token_service


async def _create_patient(
    db: AsyncSession, *, national_id: str = "0013542419"
) -> User:
    from tests.auth_helpers import phone_from_seed

    user = User(
        email=f"patient_{national_id}@patient.local",
        hashed_password=get_password_hash("PatientPass123!"),
        full_name=f"بیمار {national_id[-4:]}",
        national_id=national_id,
        phone=phone_from_seed(f"refresh-{national_id}"),
        role=UserRole.PATIENT,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _login(
    async_client: AsyncClient, *, national_id: str = "0013542419"
) -> dict:
    response = await async_client.post(
        "/api/auth/login",
        json={"national_id": national_id, "password": "PatientPass123!"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("access_token")
    assert body.get("refresh_token")
    assert isinstance(body.get("expires_in"), int) and body["expires_in"] > 0
    assert (
        isinstance(body.get("refresh_expires_in"), int)
        and body["refresh_expires_in"] > 0
    )
    return body


@pytest.mark.asyncio
async def test_login_issues_refresh_token(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    await _create_patient(db)
    body = await _login(async_client)

    rows = (
        await db.execute(select(RefreshToken).where(RefreshToken.user_id.is_not(None)))
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].token_hash == refresh_token_service.hash_refresh_token(
        body["refresh_token"]
    )
    assert rows[0].rotated_at is None
    assert rows[0].revoked_at is None


@pytest.mark.asyncio
async def test_refresh_rotates_token(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    await _create_patient(db)
    login_body = await _login(async_client)
    old_refresh = login_body["refresh_token"]

    refresh = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh.status_code == 200, refresh.text
    new_body = refresh.json()
    assert new_body["access_token"]
    assert new_body["refresh_token"]
    assert new_body["refresh_token"] != old_refresh

    rows = (await db.execute(select(RefreshToken))).scalars().all()
    assert len(rows) == 2
    old_row = next(
        r
        for r in rows
        if r.token_hash
        == refresh_token_service.hash_refresh_token(old_refresh)
    )
    assert old_row.rotated_at is not None
    assert old_row.revoked_at is None


@pytest.mark.asyncio
async def test_refresh_reuse_revokes_family_and_audits(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    user = await _create_patient(db)
    login_body = await _login(async_client)
    old_refresh = login_body["refresh_token"]

    first = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]

    reuse = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert reuse.status_code == 401
    assert "reuse" in reuse.json()["detail"].lower()

    rows = (await db.execute(select(RefreshToken))).scalars().all()
    assert rows
    assert all(r.revoked_at is not None for r in rows)

    # New token from the same family must also be dead.
    dead = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert dead.status_code == 401

    audits = (
        await db.execute(
            select(AuditLog).where(
                AuditLog.action == refresh_token_service.AUDIT_REFRESH_TOKEN_REUSE
            )
        )
    ).scalars().all()
    assert len(audits) >= 1
    assert audits[0].user_id == user.id


@pytest.mark.asyncio
async def test_logout_revokes_current_family(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    await _create_patient(db)
    login_body = await _login(async_client)
    refresh = login_body["refresh_token"]

    logout = await async_client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh},
    )
    assert logout.status_code == 200

    again = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert again.status_code == 401

    row = (await db.execute(select(RefreshToken))).scalar_one()
    assert row.revoked_at is not None


@pytest.mark.asyncio
async def test_logout_all_revokes_every_family(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    user = await _create_patient(db)
    first = await _login(async_client)
    second = await _login(async_client)

    access = first["access_token"]
    logout_all = await async_client.post(
        "/api/auth/logout-all",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert logout_all.status_code == 200

    for token in (first["refresh_token"], second["refresh_token"]):
        resp = await async_client.post(
            "/api/auth/refresh",
            json={"refresh_token": token},
        )
        assert resp.status_code == 401

    rows = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert all(r.revoked_at is not None for r in rows)


@pytest.mark.asyncio
async def test_refresh_rejects_idle_expired_token(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    await _create_patient(db)
    monkeypatch.setattr(config_module.settings, "refresh_token_idle_minutes", 60)
    login_body = await _login(async_client)
    raw = login_body["refresh_token"]

    row = (await db.execute(select(RefreshToken))).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
    await db.commit()

    expired = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": raw},
    )
    assert expired.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rejects_absolute_lifetime(
    async_client: AsyncClient, db: AsyncSession, monkeypatch
) -> None:
    await _create_patient(db)
    monkeypatch.setattr(config_module.settings, "refresh_token_absolute_days", 7)
    login_body = await _login(async_client)
    raw = login_body["refresh_token"]

    row = (await db.execute(select(RefreshToken))).scalar_one()
    # Force family origin past absolute window while idle expiry still looks valid.
    row.issued_at = datetime.now(timezone.utc) - timedelta(days=8)
    row.expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    await db.commit()

    expired = await async_client.post(
        "/api/auth/refresh",
        json={"refresh_token": raw},
    )
    assert expired.status_code == 401


@pytest.mark.asyncio
async def test_cleanup_expired_refresh_tokens(
    async_client: AsyncClient, db: AsyncSession
) -> None:
    await _create_patient(db)
    await _login(async_client)

    row = (await db.execute(select(RefreshToken))).scalar_one()
    row.issued_at = datetime.now(timezone.utc) - timedelta(days=30)
    row.expires_at = datetime.now(timezone.utc) - timedelta(days=29)
    await db.commit()

    deleted = await refresh_token_service.cleanup_expired_refresh_tokens(db)
    assert deleted >= 1
    remaining = (await db.execute(select(RefreshToken))).scalars().all()
    assert remaining == []
