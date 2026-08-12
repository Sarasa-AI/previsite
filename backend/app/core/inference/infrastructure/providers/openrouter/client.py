"""OpenRouter HTTP client — async provider transport layer."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.inference.infrastructure.providers.openrouter.errors import (
    OpenRouterAuthError,
    OpenRouterHTTPError,
    OpenRouterRateLimitError,
    OpenRouterResponseError,
    OpenRouterStructuredOutputError,
    OpenRouterTimeoutError,
    OpenRouterTransportError,
)
from app.core.inference.infrastructure.providers.openrouter.models import (
    OpenRouterCompletionResponse,
    OpenRouterMessage,
    OpenRouterStructuredOutput,
)

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Async HTTP client for OpenRouter chat completions API.

    Parameters
    ----------
    api_key : str
        OpenRouter API key (required, validated at construction).
    base_url : str
        OpenRouter base URL.
    model : str
        Model identifier to use for completions.
    timeout : float
        Request timeout in seconds.
    http_referer : str
        HTTP-Referer header value.
    app_title : str
        X-Title header value.

    Raises
    ------
    ValueError
        If api_key is empty or None.

    Notes
    -----
    The API key is never exposed in logs, exception messages, or response metadata.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        http_referer: str,
        app_title: str,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("OpenRouter API key must not be empty")

        self._api_key = api_key.strip()
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._http_referer = http_referer
        self._app_title = app_title

        self._client = httpx.AsyncClient(timeout=self._timeout)

    @property
    def model(self) -> str:
        """Model identifier used for completions."""
        return self._model

    @property
    def base_url(self) -> str:
        """OpenRouter base URL."""
        return self._base_url

    async def complete(
        self,
        messages: tuple[OpenRouterMessage, ...],
    ) -> OpenRouterStructuredOutput:
        """Execute a chat completion request and return validated structured output.

        Parameters
        ----------
        messages : tuple[OpenRouterMessage, ...]
            Conversation messages.

        Returns
        -------
        OpenRouterStructuredOutput
            Validated structured model output.

        Raises
        ------
        OpenRouterAuthError
            401 Unauthorized.
        OpenRouterRateLimitError
            429 Too Many Requests.
        OpenRouterTimeoutError
            Request timeout.
        OpenRouterTransportError
            Network/transport failure.
        OpenRouterHTTPError
            Other HTTP error (4xx/5xx).
        OpenRouterResponseError
            Malformed API response.
        OpenRouterStructuredOutputError
            Invalid structured output from model.
        """
        url = f"{self._base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self._http_referer,
            "X-Title": self._app_title,
        }

        payload = {
            "model": self._model,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            response = await self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise OpenRouterTimeoutError(
                f"OpenRouter request timed out after {self._timeout}s"
            ) from exc
        except (httpx.ConnectError, httpx.NetworkError) as exc:
            raise OpenRouterTransportError(
                f"OpenRouter transport failure: {type(exc).__name__}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OpenRouterTransportError(
                f"OpenRouter HTTP transport error: {type(exc).__name__}"
            ) from exc

        # Handle HTTP status errors
        if response.status_code == 401:
            raise OpenRouterAuthError("Authentication failed (401 Unauthorized)")
        elif response.status_code == 429:
            retry_after = self._parse_retry_after(response.headers)
            raise OpenRouterRateLimitError(
                "Rate limit exceeded (429 Too Many Requests)",
                retry_after=retry_after,
            )
        elif not (200 <= response.status_code < 300):
            raise OpenRouterHTTPError(
                f"HTTP error {response.status_code}",
                status_code=response.status_code,
            )

        # Parse provider response
        try:
            response_data = response.json()
        except Exception as exc:
            raise OpenRouterResponseError(
                "Failed to parse JSON response from OpenRouter"
            ) from exc

        try:
            completion_response = OpenRouterCompletionResponse.model_validate(response_data)
        except ValidationError as exc:
            raise OpenRouterResponseError(
                f"Invalid OpenRouter response structure: {exc}"
            ) from exc

        # Extract and validate structured output
        if not completion_response.choices:
            raise OpenRouterResponseError("OpenRouter response contains no choices")

        choice = completion_response.choices[0]
        content = choice.message.content

        if not content or not content.strip():
            raise OpenRouterResponseError("OpenRouter response content is empty")

        # Parse and validate structured JSON
        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenRouterStructuredOutputError(
                f"Model output is not valid JSON: {exc}"
            ) from exc

        try:
            structured_output = OpenRouterStructuredOutput.model_validate(parsed_json)
        except ValidationError as exc:
            raise OpenRouterStructuredOutputError(
                f"Model output does not match expected schema: {exc}"
            ) from exc

        return structured_output

    @staticmethod
    def _parse_retry_after(headers: httpx.Headers) -> int | None:
        """Extract Retry-After header value if present."""
        retry_after_str = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after_str:
            try:
                return int(retry_after_str)
            except ValueError:
                return None
        return None

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
