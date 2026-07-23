"""Seed the default doctor account from environment variables.

Usage (from backend/):
  SEED_DOCTOR_PASSWORD=... python init_doctor.py
"""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.db.init_db import _seed_default_doctor


async def _main() -> None:
    if not (settings.seed_doctor_password or "").strip():
        print(
            "ERROR: Set SEED_DOCTOR_PASSWORD before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)
    await _seed_default_doctor()
    username = settings.seed_doctor_username
    print(f"Doctor seed ensured for username={username!r} email={username}@doctor.com")


if __name__ == "__main__":
    asyncio.run(_main())
