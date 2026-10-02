"""Consent ledger service — append-only grant/withdraw + enforcement gate."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.session_access import is_patient
from app.core.config import settings
from app.models.patient_consent import PatientConsent
from app.models.user import User
from app.privacy.consent_keys import (
    ALL_CONSENT_KEYS,
    CONSENT_REQUIRED_CODE,
    ENFORCEMENT_REQUIRED_KEYS,
    copy_text_key_for,
    current_version_for,
    is_known_consent_key,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def list_consent_records(
    db: AsyncSession, user_id: int
) -> list[PatientConsent]:
    """Return the full append-only history for a user (oldest first)."""
    result = await db.execute(
        select(PatientConsent)
        .where(PatientConsent.user_id == user_id)
        .order_by(PatientConsent.id.asc())
    )
    return list(result.scalars().all())


async def _latest_per_key(
    db: AsyncSession, user_id: int
) -> dict[str, PatientConsent]:
    result = await db.execute(
        select(PatientConsent)
        .where(PatientConsent.user_id == user_id)
        .order_by(PatientConsent.id.desc())
    )
    latest: dict[str, PatientConsent] = {}
    for row in result.scalars().all():
        if row.consent_key not in latest:
            latest[row.consent_key] = row
    return latest


def _is_current_grant(row: PatientConsent | None, key: str) -> bool:
    if row is None:
        return False
    if not row.granted:
        return False
    return row.policy_version == current_version_for(key)


async def get_consent_status(
    db: AsyncSession, user_id: int
) -> list[dict]:
    """Per-key status against currently required policy versions."""
    latest = await _latest_per_key(db, user_id)
    statuses: list[dict] = []
    for key in ALL_CONSENT_KEYS:
        version = current_version_for(key)
        row = latest.get(key)
        current = _is_current_grant(row, key)
        statuses.append(
            {
                "consent_key": key,
                "policy_version": version,
                "copy_text_key": copy_text_key_for(key, version),
                "granted": current,
                "granted_at": row.granted_at if current and row else None,
                "withdrawn_at": (
                    row.withdrawn_at
                    if row and not row.granted
                    else None
                ),
                "latest_record_id": row.id if row else None,
                "latest_policy_version": row.policy_version if row else None,
            }
        )
    return statuses


async def missing_required_consents(
    db: AsyncSession,
    user_id: int,
    *,
    keys: Sequence[str] | None = None,
) -> list[str]:
    required = tuple(keys) if keys is not None else ENFORCEMENT_REQUIRED_KEYS
    latest = await _latest_per_key(db, user_id)
    missing: list[str] = []
    for key in required:
        if not is_known_consent_key(key):
            continue
        if not _is_current_grant(latest.get(key), key):
            missing.append(key)
    return missing


async def grant_consent(
    db: AsyncSession,
    *,
    user_id: int,
    consent_key: str,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    policy_version: Optional[str] = None,
) -> PatientConsent:
    if not is_known_consent_key(consent_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNKNOWN_CONSENT_KEY", "consent_key": consent_key},
        )
    version = policy_version or current_version_for(consent_key)
    now = _utcnow()
    row = PatientConsent(
        user_id=user_id,
        consent_key=consent_key,
        policy_version=version,
        granted=True,
        granted_at=now,
        withdrawn_at=None,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def withdraw_consent(
    db: AsyncSession,
    *,
    user_id: int,
    consent_key: str,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> PatientConsent:
    """Append a withdrawal record — never mutate prior grants."""
    if not is_known_consent_key(consent_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "UNKNOWN_CONSENT_KEY", "consent_key": consent_key},
        )
    version = current_version_for(consent_key)
    latest = await _latest_per_key(db, user_id)
    prior = latest.get(consent_key)
    # Preserve the policy version that was last acted on when withdrawing an
    # older grant; otherwise stamp current required version.
    if prior is not None:
        version = prior.policy_version
    now = _utcnow()
    row = PatientConsent(
        user_id=user_id,
        consent_key=consent_key,
        policy_version=version,
        granted=False,
        granted_at=None,
        withdrawn_at=now,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def require_patient_consents(
    db: AsyncSession,
    user: User,
    *,
    keys: Iterable[str] | None = None,
) -> None:
    """API-boundary gate. No-op when enforcement is off or user is not a patient."""
    if not settings.consent_enforcement_enabled:
        return
    if not is_patient(user):
        return

    required = tuple(keys) if keys is not None else ENFORCEMENT_REQUIRED_KEYS
    missing = await missing_required_consents(db, user.id, keys=required)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": CONSENT_REQUIRED_CODE,
                "missing": missing,
            },
        )
