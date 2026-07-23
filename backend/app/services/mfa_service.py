"""TOTP MFA helpers for doctor accounts."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import timedelta
from typing import Optional

import pyotp

from app.auth.security import create_access_token, decode_access_token
from app.core.config import settings

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
    secret: Optional[str] = None,
) -> str:
    payload: dict = {
        "sub": str(user_id),
        "purpose": purpose,
    }
    if secret:
        payload["mfa_secret"] = secret
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
    return payload


def mfa_feature_enabled() -> bool:
    return bool(settings.mfa_enabled)
