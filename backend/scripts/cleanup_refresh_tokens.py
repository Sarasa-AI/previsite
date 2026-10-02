#!/usr/bin/env python3
"""Delete refresh tokens past absolute family lifetime (operator-run).

No scheduler — invoke periodically from cron or ops runbooks.

Usage:
  python scripts/cleanup_refresh_tokens.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.refresh_token_service import (  # noqa: E402
    cleanup_expired_refresh_tokens,
)

logger = logging.getLogger(__name__)


async def _async_main() -> int:
    deleted = await cleanup_expired_refresh_tokens()
    print(f"Deleted {deleted} expired refresh token row(s).")
    return 0


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(asyncio.run(_async_main()))


if __name__ == "__main__":
    main()
