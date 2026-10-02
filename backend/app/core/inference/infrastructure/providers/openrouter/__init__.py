"""OpenRouter inference provider — infrastructure implementation."""

from __future__ import annotations

from app.core.inference.infrastructure.providers.openrouter.adapter import (
    OpenRouterInferenceAdapter,
)
from app.core.inference.infrastructure.providers.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterError,
    OpenRouterHTTPError,
    OpenRouterRateLimitError,
    OpenRouterResponseError,
    OpenRouterStructuredOutputError,
    OpenRouterTimeoutError,
    OpenRouterTransportError,
)

__all__ = [
    "OpenRouterInferenceAdapter",
    "OpenRouterError",
    "OpenRouterAuthError",
    "OpenRouterRateLimitError",
    "OpenRouterTimeoutError",
    "OpenRouterTransportError",
    "OpenRouterHTTPError",
    "OpenRouterResponseError",
    "OpenRouterStructuredOutputError",
]
