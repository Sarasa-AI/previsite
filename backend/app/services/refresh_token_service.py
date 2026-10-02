"""Opaque rotating refresh tokens — plaintext never stored."""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.refresh_token import RefreshToken

logger = logging.getLogger(__name__)

AUDIT_REFRESH_TOKEN_REUSE = "refresh_token_reuse"


class RefreshTokenError(Exception):
    """Base refresh-token failure (invalid / expired / revoked)."""


class RefreshTokenReuseError(RefreshTokenError):
    """Presented token was already rotated — family revoked."""

    def __init__(self, message: str = "Refresh token reuse detected", *, user_id: int | None = None):
        super().__init__(message)
        self.user_id = user_id


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_raw_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def _idle_delta() -> timedelta:
    return timedelta(minutes=int(settings.REFRESH_TOKEN_IDLE_MINUTES))


def _absolute_delta() -> timedelta:
    return timedelta(days=int(settings.REFRESH_TOKEN_ABSOLUTE_DAYS))


async def _family_origin(db: AsyncSession, family_id: str) -> datetime | None:
    result = await db.execute(
        select(func.min(RefreshToken.issued_at)).where(
            RefreshToken.family_id == family_id
        )
    )
    origin = result.scalar_one_or_none()
    return _as_utc(origin) if origin is not None else None


def _compute_expires_at(
    *,
    now: datetime,
    family_origin: datetime,
) -> datetime:
    idle_deadline = now + _idle_delta()
    absolute_deadline = _as_utc(family_origin) + _absolute_delta()
    return min(idle_deadline, absolute_deadline)


async def issue_refresh_token(
    db: AsyncSession,
    *,
    user_id: int,
    family_id: str | None = None,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, int]:
    """Create a new refresh token (new or continuing family).

    Returns (raw_token, expires_in_seconds). Caller must persist via commit
    if the session was not committed here — this function commits.
    """
    now = _utcnow()
    if family_id is None:
        family_id = str(uuid.uuid4())
        family_origin = now
    else:
        origin = await _family_origin(db, family_id)
        family_origin = origin or now

    expires_at = _compute_expires_at(now=now, family_origin=family_origin)
    if expires_at <= now:
        raise RefreshTokenError("Refresh session absolute lifetime exceeded")

    raw = generate_raw_refresh_token()
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=hash_refresh_token(raw),
        issued_at=now,
        expires_at=expires_at,
        user_agent=(user_agent[:512] if user_agent else None),
        ip=(ip[:64] if ip else None),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    expires_in = max(1, int((expires_at - now).total_seconds()))
    return raw, expires_in


async def revoke_family(
    db: AsyncSession,
    *,
    family_id: str,
    when: datetime | None = None,
) -> int:
    """Revoke all tokens in a family. Returns rows updated."""
    now = when or _utcnow()
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()
    return int(result.rowcount or 0)


async def revoke_all_for_user(db: AsyncSession, *, user_id: int) -> int:
    """Revoke every refresh-token family for a user."""
    now = _utcnow()
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await db.commit()
    return int(result.rowcount or 0)


async def revoke_all_families_for_user(db: AsyncSession, *, user_id: int) -> int:
    """Alias for Task 5 naming — revokes all refresh families for a user."""
    return await revoke_all_for_user(db, user_id=user_id)


async def rotate_refresh_token(
    db: AsyncSession,
    *,
    raw_token: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> tuple[str, int, int]:
    """Validate and rotate a refresh token.

    Returns (new_raw_token, expires_in_seconds, user_id).
    Reuse of an already-rotated token revokes the family and raises
    RefreshTokenReuseError.
    """
    now = _utcnow()
    token_hash = hash_refresh_token(raw_token.strip())
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise RefreshTokenError("Invalid refresh token")

    if row.rotated_at is not None:
        await revoke_family(db, family_id=row.family_id, when=now)
        raise RefreshTokenReuseError(
            "Refresh token reuse detected",
            user_id=row.user_id,
        )

    if row.revoked_at is not None:
        raise RefreshTokenError("Refresh token revoked")

    expires_at = _as_utc(row.expires_at)
    if expires_at <= now:
        raise RefreshTokenError("Refresh token expired")

    family_origin = await _family_origin(db, row.family_id)
    if family_origin is None:
        family_origin = _as_utc(row.issued_at)

    absolute_deadline = family_origin + _absolute_delta()
    if absolute_deadline <= now:
        await revoke_family(db, family_id=row.family_id, when=now)
        raise RefreshTokenError("Refresh session absolute lifetime exceeded")

    row.rotated_at = now
    await db.commit()

    new_raw, expires_in = await issue_refresh_token(
        db,
        user_id=row.user_id,
        family_id=row.family_id,
        user_agent=user_agent,
        ip=ip,
    )
    return new_raw, expires_in, row.user_id


async def revoke_current_family_from_token(
    db: AsyncSession,
    *,
    raw_token: str,
) -> bool:
    """Revoke the family owning this token. Returns False if unknown."""
    token_hash = hash_refresh_token(raw_token.strip())
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return False
    await revoke_family(db, family_id=row.family_id)
    return True


async def _cleanup_expired(db: AsyncSession) -> int:
    now = _utcnow()
    cutoff = now - _absolute_delta()
    # Families whose earliest issued_at is older than absolute lifetime.
    # Rotated rows are kept until then so reuse detection still works.
    stale_families = (
        select(RefreshToken.family_id)
        .group_by(RefreshToken.family_id)
        .having(func.min(RefreshToken.issued_at) < cutoff)
    )
    result = await db.execute(
        delete(RefreshToken).where(RefreshToken.family_id.in_(stale_families))
    )
    await db.commit()
    deleted = int(result.rowcount or 0)
    logger.info("cleanup_expired_refresh_tokens deleted=%s", deleted)
    return deleted


async def cleanup_expired_refresh_tokens(db: AsyncSession | None = None) -> int:
    """Delete refresh tokens past the absolute family lifetime.

    Callable from scripts; no scheduler. When ``db`` is omitted, opens a
    short-lived session via ``get_async_session``.
    """
    if db is not None:
        return await _cleanup_expired(db)

    from app.db.database import get_async_session

    async with get_async_session() as session:
        return await _cleanup_expired(session)
