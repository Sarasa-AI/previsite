"""TOTP MFA helpers for doctor accounts."""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, decode_access_token
from app.core.config import settings
from app.models.mfa_setup_challenge import MfaSetupChallenge
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

MFA_CHALLENGE_MINUTES = 10
BACKUP_CODE_COUNT = 10
ISSUER_NAME = "PreVisit"


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_uri(*, secret: str, account_name: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=account_name, issuer_name=ISSUER_NAME)


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return bool(totp.verify(code.strip(), valid_window=1))


def generate_backup_codes(count: int = BACKUP_CODE_COUNT) -> list[str]:
    return [secrets.token_hex(4) for _ in range(count)]


def hash_backup_code(code: str) -> str:
    return hashlib.sha256(code.strip().lower().encode("utf-8")).hexdigest()


def serialize_backup_hashes(codes: list[str]) -> str:
    return json.dumps([hash_backup_code(c) for c in codes])


def load_backup_hashes(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def consume_backup_code(raw_hashes: Optional[str], code: str) -> tuple[bool, Optional[str]]:
    """Return (consumed, updated_json_or_none)."""
    hashes = load_backup_hashes(raw_hashes)
    target = hash_backup_code(code)
    if target not in hashes:
        return False, raw_hashes
    hashes.remove(target)
    return True, json.dumps(hashes)


def create_mfa_challenge_token(
    *,
    user_id: int,
    purpose: str,
    challenge_id: Optional[str] = None,
) -> str:
    """Build a short-lived MFA challenge JWT.

    Setup challenges must pass ``challenge_id`` only — never embed the TOTP
    secret in the token. Verify challenges need no extra claims.
    """
    payload: dict = {
        "sub": str(user_id),
        "purpose": purpose,
    }
    if challenge_id:
        payload["challenge_id"] = challenge_id
    return create_access_token(
        payload,
        expires_delta=timedelta(minutes=MFA_CHALLENGE_MINUTES),
    )


def decode_mfa_challenge_token(token: str, *, expected_purpose: str) -> Optional[dict]:
    payload = decode_access_token(token)
    if not payload:
        return None
    if payload.get("purpose") != expected_purpose:
        return None
    # Never accept legacy tokens that still carry secret material.
    if "mfa_secret" in payload:
        logger.warning("Rejected MFA challenge token containing secret material")
        return None
    return payload


async def create_setup_challenge(
    db: AsyncSession,
    *,
    user_id: int,
    secret: str,
) -> str:
    """Persist an encrypted pending secret; return challenge_id for the JWT."""
    challenge_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=MFA_CHALLENGE_MINUTES)
    row = MfaSetupChallenge(
        id=challenge_id,
        user_id=user_id,
        secret_encrypted=encrypt_mfa_secret_for_storage(secret),
        expires_at=expires_at,
    )
    db.add(row)
    await db.commit()
    return challenge_id


async def load_setup_challenge_secret(
    db: AsyncSession,
    *,
    challenge_id: str,
    user_id: int,
) -> Optional[str]:
    """Return plaintext secret if challenge is valid, unused, and unexpired.

    Does not mark the challenge consumed — call ``mark_setup_challenge_consumed``
    after successful TOTP verification. Never raises secret material into logs.
    """
    if not challenge_id or not isinstance(challenge_id, str):
        return None
    result = await db.execute(
        select(MfaSetupChallenge).where(MfaSetupChallenge.id == challenge_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    if row.user_id != user_id:
        return None
    if row.consumed_at is not None:
        return None
    now = datetime.now(timezone.utc)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        return None
    try:
        secret = decrypt_mfa_secret_from_storage(row.secret_encrypted)
    except Exception:
        logger.exception("Failed to decrypt MFA setup challenge")
        return None
    return secret or None


async def mark_setup_challenge_consumed(
    db: AsyncSession,
    *,
    challenge_id: str,
    user_id: int,
) -> bool:
    """Mark challenge single-use consumed. Returns False if already used/missing."""
    result = await db.execute(
        select(MfaSetupChallenge).where(MfaSetupChallenge.id == challenge_id)
    )
    row = result.scalar_one_or_none()
    if row is None or row.user_id != user_id or row.consumed_at is not None:
        return False
    row.consumed_at = datetime.now(timezone.utc)
    await db.commit()
    return True


async def consume_setup_challenge(
    db: AsyncSession,
    *,
    challenge_id: str,
    user_id: int,
) -> Optional[str]:
    """Load and immediately consume a challenge (single-use)."""
    secret = await load_setup_challenge_secret(
        db, challenge_id=challenge_id, user_id=user_id
    )
    if not secret:
        return None
    if not await mark_setup_challenge_consumed(
        db, challenge_id=challenge_id, user_id=user_id
    ):
        return None
    return secret


def mfa_feature_enabled() -> bool:
    return bool(
        settings.mfa_enabled
        or settings.doctor_mfa_required
        or settings.admin_mfa_required
    )


def user_requires_mfa(user: User) -> bool:
    """Role-specific MFA requirement (legacy MFA_ENABLED implies doctor MFA)."""
    if user.role == UserRole.DOCTOR:
        return bool(settings.doctor_mfa_required or settings.mfa_enabled)
    if user.role == UserRole.ADMIN:
        return bool(settings.admin_mfa_required)
    return False


def privileged_mfa_enrollment_role(user: User) -> bool:
    return user.role in (UserRole.DOCTOR, UserRole.ADMIN)


def encrypt_mfa_secret_for_storage(plaintext: str) -> str:
    """Encrypt for DB storage when a key is configured; otherwise store plaintext."""
    from app.security.field_crypto import encrypt_field, validate_fernet_key

    key = (settings.field_encryption_key or "").strip() or None
    if not validate_fernet_key(key):
        return plaintext
    return encrypt_field(plaintext, key)  # type: ignore[arg-type]


def decrypt_mfa_secret_from_storage(stored: Optional[str]) -> Optional[str]:
    """Decrypt version-prefixed secrets; legacy plaintext passes through."""
    from app.security.field_crypto import decrypt_field, is_encrypted, validate_fernet_key

    if stored is None:
        return None
    key = (settings.field_encryption_key or "").strip() or None
    if not validate_fernet_key(key):
        if is_encrypted(stored):
            raise ValueError(
                "FIELD_ENCRYPTION_KEY required to read encrypted mfa_secret"
            )
        return stored
    return decrypt_field(stored, key)


def maybe_reencrypt_legacy_mfa_secret(user) -> bool:
    """If stored secret is legacy plaintext and a key exists, rewrite encrypted.

    Returns True when the ORM field was updated (caller should commit).
    """
    from app.security.field_crypto import is_encrypted, validate_fernet_key

    stored = getattr(user, "mfa_secret", None)
    if not stored or is_encrypted(stored):
        return False
    key = (settings.field_encryption_key or "").strip() or None
    if not validate_fernet_key(key):
        return False
    user.mfa_secret = encrypt_mfa_secret_for_storage(stored)
    return True
