"""OpenRouter HTTP client — routes through llm_egress_gateway."""

from __future__ import annotations

import json
import logging
from typing import Any

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
    OpenRouterMessage,
    OpenRouterStructuredOutput,
)
from app.privacy.llm_egress_gateway import (
    LlmEgressError,
    LlmImageEgressBlocked,
    LlmProviderNotAllowed,
    chat_completion,
)

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Async client for OpenRouter chat completions via the de-id gateway."""

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

    @property
    def model(self) -> str:
        return self._model

    @property
    def base_url(self) -> str:
        return self._base_url

    async def complete(
        self,
        messages: tuple[OpenRouterMessage, ...],
    ) -> OpenRouterStructuredOutput:
        payload_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]
        try:
            result = await chat_completion(
                base_url=self._base_url,
                api_key=self._api_key,
                model=self._model,
                messages=payload_messages,
                purpose="document_intelligence",
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"},
            )
        except LlmImageEgressBlocked as exc:
            raise OpenRouterHTTPError(str(exc), status_code=403) from exc
        except LlmProviderNotAllowed as exc:
            raise OpenRouterHTTPError(str(exc), status_code=403) from exc
        except LlmEgressError as exc:
            msg = str(exc).lower()
            if "401" in msg or "auth" in msg:
                raise OpenRouterAuthError("Authentication failed (401 Unauthorized)") from exc
            if "429" in msg or "rate" in msg:
                raise OpenRouterRateLimitError(
                    "Rate limit exceeded (429 Too Many Requests)"
                ) from exc
            if "timeout" in msg:
                raise OpenRouterTimeoutError(
                    f"OpenRouter request timed out after {self._timeout}s"
                ) from exc
            raise OpenRouterTransportError(
                f"OpenRouter transport failure: {exc}"
            ) from exc

        content = result.content
        if not content or not content.strip():
            raise OpenRouterResponseError("OpenRouter response content is empty")

        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenRouterStructuredOutputError(
                f"Model output is not valid JSON: {exc}"
            ) from exc

        try:
            return OpenRouterStructuredOutput.model_validate(parsed_json)
        except ValidationError as exc:
            raise OpenRouterStructuredOutputError(
                f"Model output does not match expected schema: {exc}"
            ) from exc

    async def close(self) -> None:
        """No-op — gateway owns shared clients."""
        return None
