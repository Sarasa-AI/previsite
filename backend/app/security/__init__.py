"""Generic Fernet field encryption with versioned ciphertext prefixes.

Applied in P1 only to User.mfa_secret. Designed for reuse by later phases.
Never log plaintext secrets or encryption keys.
"""

from __future__ import annotations

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

VERSION_PREFIX = "v1:"


class FieldCryptoError(Exception):
    """Raised when encryption/decryption cannot proceed safely."""


def is_encrypted(value: Optional[str]) -> bool:
    return bool(value) and value.startswith(VERSION_PREFIX)


def encrypt_field(plaintext: str, key: str) -> str:
    if plaintext is None:
        raise FieldCryptoError("Cannot encrypt None")
    if is_encrypted(plaintext):
        return plaintext
    fernet = _fernet_from_key(key)
    token = fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{VERSION_PREFIX}{token}"


def decrypt_field(value: Optional[str], key: Optional[str]) -> Optional[str]:
    """Decrypt a version-prefixed value, or return legacy plaintext unchanged."""
    if value is None:
        return None
    if not is_encrypted(value):
        return value
    if not key:
        raise FieldCryptoError("Encrypted field requires FIELD_ENCRYPTION_KEY")
    ciphertext = value[len(VERSION_PREFIX) :]
    fernet = _fernet_from_key(key)
    try:
        return fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise FieldCryptoError("Decryption failed (wrong key or corrupt ciphertext)") from exc


def validate_fernet_key(key: Optional[str]) -> bool:
    if not key or not str(key).strip():
        return False
    try:
        _fernet_from_key(key.strip())
        return True
    except Exception:
        return False


def _fernet_from_key(key: str) -> Fernet:
    raw = (key or "").strip().encode("utf-8")
    try:
        return Fernet(raw)
    except Exception as exc:
        raise FieldCryptoError("Invalid FIELD_ENCRYPTION_KEY") from exc
