#!/usr/bin/env python3
"""Delete llm_egress_log rows older than LLM_EGRESS_LOG_RETENTION_DAYS.

No scheduler — run manually / from cron:
  PYTHONPATH=. python scripts/cleanup_llm_egress_log.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.models.llm_egress_log import LlmEgressLog


async def main() -> None:
    days = max(1, int(settings.llm_egress_log_retention_days))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(LlmEgressLog).where(LlmEgressLog.created_at < cutoff)
        )
        await db.commit()
        print(f"Deleted llm_egress_log rows older than {days} days (cutoff={cutoff.isoformat()})")
        print(f"rowcount={result.rowcount}")


if __name__ == "__main__":
    asyncio.run(main())
