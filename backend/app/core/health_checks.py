"""Dependency health probes for the admin detailed health endpoint."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from openai import APIConnectionError, AuthenticationError, AsyncOpenAI
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


async def check_ollama() -> dict[str, Any]:
    host = (settings.ollama_host or "").rstrip("/")
    if not host:
        return {"status": "down", "error": "OLLAMA_HOST not configured"}
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{host}/api/tags")
            if response.status_code < 500:
                return {"status": "ok", "http_status": response.status_code}
            return {"status": "degraded", "http_status": response.status_code}
    except Exception as exc:
        logger.warning("Detailed health Ollama check failed: %s", type(exc).__name__)
        return {"status": "down", "error": type(exc).__name__}


async def check_llm_provider() -> dict[str, Any]:
    provider = settings.llm_provider
    if not is_openrouter_api_key_configured():
        return {
            "status": "degraded",
            "provider": provider,
            "error": "OPENROUTER_API_KEY not configured",
        }

    http_client_kwargs: dict[str, Any] = {"timeout": 5.0}
    if settings.HTTP_PROXY and settings.HTTP_PROXY.strip():
        http_client_kwargs["proxies"] = settings.HTTP_PROXY
    http_client = httpx.AsyncClient(**http_client_kwargs)
    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        max_retries=0,
        http_client=http_client,
    )
    try:
        models = await client.models.list()
        model_count = len(getattr(models, "data", []) or [])
        return {
            "status": "ok",
            "provider": provider,
            "available_models": model_count,
        }
    except AuthenticationError:
        return {"status": "down", "provider": provider, "error": "authentication_failed"}
    except APIConnectionError:
        return {"status": "down", "provider": provider, "error": "connection_error"}
    except Exception as exc:
        return {"status": "down", "provider": provider, "error": type(exc).__name__}
    finally:
        await client.close()
        await http_client.aclose()
