#!/usr/bin/env python3
"""Encrypt remaining plaintext MFA secrets at rest (operator-run, idempotent).

Never prints secrets or keys. Safe to re-run. Not invoked by migrations/startup.

Usage:
  FIELD_ENCRYPTION_KEY=... python scripts/encrypt_mfa_secrets.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.database import get_async_session  # noqa: E402
from app.models.user import User  # noqa: E402
from app.security.field_crypto import is_encrypted, validate_fernet_key  # noqa: E402
from app.services import mfa_service  # noqa: E402

logger = logging.getLogger(__name__)


async def encrypt_plaintext_mfa_secrets() -> int:
    key = (settings.field_encryption_key or "").strip() or None
    if not validate_fernet_key(key):
        raise SystemExit(
            "FIELD_ENCRYPTION_KEY must be set to a valid Fernet key before running."
        )

    updated = 0
    async with get_async_session() as db:
        result = await db.execute(
            select(User).where(User.mfa_secret.is_not(None))
        )
        users = list(result.scalars().all())
        for user in users:
            stored = user.mfa_secret
            if not stored or is_encrypted(stored):
                continue
            user.mfa_secret = mfa_service.encrypt_mfa_secret_for_storage(stored)
            updated += 1
        if updated:
            await db.commit()
    return updated


async def _async_main() -> int:
    count = await encrypt_plaintext_mfa_secrets()
    print(f"Encrypted {count} plaintext mfa_secret value(s).")
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    return asyncio.run(_async_main())


if __name__ == "__main__":
    raise SystemExit(main())
