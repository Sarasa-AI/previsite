import logging

import httpx
from openai import APIConnectionError, AuthenticationError, AsyncOpenAI

from app.core.config import is_openrouter_api_key_configured, settings

logger = logging.getLogger(__name__)


async def verify_llm_connection() -> None:
    """Ping OpenRouter to verify API key validity and proxy routing before accepting traffic."""
    if not is_openrouter_api_key_configured():
        logger.warning(
            "OpenRouter health check skipped: OPENROUTER_API_KEY is not configured."
        )
        return

    http_client = httpx.AsyncClient(proxies=settings.HTTP_PROXY, timeout=30.0)
    client = AsyncOpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        max_retries=0,
        http_client=http_client,
        default_headers={
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        },
    )

    try:
        models = await client.models.list()
        model_count = len(getattr(models, "data", []) or [])
        proxy_route = settings.http_proxy or "direct"
        logger.info(
            "System Ready | provider=%s base_url=%s default_model=%s proxy=%s available_models=%s",
            settings.llm_provider,
            settings.openrouter_base_url,
            settings.openrouter_default_model,
            proxy_route,
            model_count,
        )
    except AuthenticationError as exc:
        logger.critical(
            "System Unhealthy | OpenRouter authentication failed. "
            "Verify OPENROUTER_API_KEY is valid. detail=%s",
            exc,
        )
        raise RuntimeError(
            "Startup health check failed: invalid OpenRouter credentials."
        ) from exc
    except APIConnectionError as exc:
        logger.critical(
            "System Unhealthy | Cannot reach OpenRouter. "
            "Check network connectivity and HTTP_PROXY settings. detail=%s",
            exc,
        )
        raise RuntimeError(
            "Startup health check failed: OpenRouter connection error."
        ) from exc
    except Exception as exc:
        logger.critical(
            "System Unhealthy | OpenRouter health check failed. detail=%s",
            exc,
        )
        raise RuntimeError("Startup health check failed.") from exc
    finally:
        await client.close()
        await http_client.aclose()
