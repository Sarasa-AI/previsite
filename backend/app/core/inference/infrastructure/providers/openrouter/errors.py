"""OpenRouter provider-specific exceptions."""

from __future__ import annotations


class OpenRouterError(Exception):
    """Base exception for all OpenRouter provider errors."""


class OpenRouterAuthError(OpenRouterError):
    """Authentication failure (401 Unauthorized)."""


class OpenRouterRateLimitError(OpenRouterError):
    """Rate limit exceeded (429 Too Many Requests).

    Attributes
    ----------
    retry_after : int | None
        Number of seconds to wait before retry, if provided by the server.
    """

    def __init__(self, message: str, retry_after: int | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class OpenRouterTimeoutError(OpenRouterError):
    """Request timeout."""


class OpenRouterTransportError(OpenRouterError):
    """Network/transport failure."""


class OpenRouterHTTPError(OpenRouterError):
    """HTTP error (non-2xx status code).

    Attributes
    ----------
    status_code : int
        HTTP status code returned by the server.
    """

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class OpenRouterResponseError(OpenRouterError):
    """Malformed or unexpected API response structure."""


class OpenRouterStructuredOutputError(OpenRouterError):
    """Invalid structured output from model (schema validation failure)."""
