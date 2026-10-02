"""Dependency health probes for the admin detailed health endpoint."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openai import APIConnectionError, AuthenticationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import is_openrouter_api_key_configured, settings

logger = logging.getLogger(__name__)


async def check_database(db: AsyncSession) -> dict[str, Any]:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("Detailed health DB check failed: %s", type(exc).__name__)
        return {"status": "down", "error": type(exc).__name__}


async def check_migrations(db: AsyncSession) -> dict[str, Any]:
    """Compare alembic_version with script head. Never raises.

    Returns status: ok | behind | unknown
    """
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg_path = Path(__file__).resolve().parents[2] / "alembic.ini"
        cfg = Config(str(cfg_path))
        script = ScriptDirectory.from_config(cfg)
        heads = set(script.get_heads())

        try:
            result = await db.execute(text("SELECT version_num FROM alembic_version"))
            rows = [row[0] for row in result.fetchall()]
        except Exception:
            logger.warning("alembic_version table unreadable", exc_info=True)
            return {"status": "unknown", "error": "alembic_version_unreadable"}

        if not rows:
            return {"status": "unknown", "db_revision": None, "heads": sorted(heads)}

        db_revisions = set(rows)
        if db_revisions == heads:
            return {
                "status": "ok",
                "db_revision": sorted(db_revisions),
                "heads": sorted(heads),
            }

        # If DB has a revision that is an ancestor of a head, report behind.
        try:
            for head in heads:
                ancestors = {rev.revision for rev in script.walk_revisions(head)}
                if db_revisions & ancestors and not (db_revisions & heads):
                    return {
                        "status": "behind",
                        "db_revision": sorted(db_revisions),
                        "heads": sorted(heads),
                    }
        except Exception:
            logger.warning("Migration ancestry walk failed", exc_info=True)

        return {
            "status": "unknown",
            "db_revision": sorted(db_revisions),
            "heads": sorted(heads),
        }
    except Exception as exc:
        logger.warning("Migration health probe failed: %s", type(exc).__name__)
        return {"status": "unknown", "error": type(exc).__name__}


async def check_llm_provider() -> dict[str, Any]:
    provider = settings.llm_provider
    if not is_openrouter_api_key_configured():
        return {
            "status": "degraded",
            "provider": provider,
            "error": "OPENROUTER_API_KEY not configured",
        }

    from app.privacy.llm_egress_gateway import LlmEgressError, list_models

    try:
        models = await list_models(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key or "",
            purpose="health_check",
        )
        model_count = len(getattr(models, "data", []) or [])
        return {
            "status": "ok",
            "provider": provider,
            "available_models": model_count,
        }
    except AuthenticationError:
        return {"status": "down", "provider": provider, "error": "authentication_failed"}
    except (APIConnectionError, LlmEgressError):
        return {"status": "down", "provider": provider, "error": "connection_error"}
    except Exception as exc:
        return {"status": "down", "provider": provider, "error": type(exc).__name__}
