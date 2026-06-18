import json
import logging

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from app.core.config import settings
from app.services.json_parser import parse_llm_json

logger = logging.getLogger(__name__)

JSON_ONLY_SUFFIX = (
    "\n\nYou MUST respond with raw JSON only. "
    "Do not wrap the response in markdown code fences or add any explanation."
)

FREE_MODEL_FALLBACKS = [
    "google/gemini-2.0-flash-lite-preview-02-05:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
]


class OpenRouterServiceError(Exception):
    """Base class for OpenRouter service failures."""


class OpenRouterAuthenticationError(OpenRouterServiceError):
    """Raised when OpenRouter credentials are missing or invalid."""


class OpenRouterService:
    """OpenRouter LLM client (OpenAI-compatible API) for structured JSON generation."""

    def __init__(self) -> None:
        self.client: AsyncOpenAI | None = None
        self.base_url = settings.openrouter_base_url

    def _model_candidates(self) -> list[str]:
        configured = settings.openrouter_default_model
        candidates = [configured]
        for model in FREE_MODEL_FALLBACKS:
            if model not in candidates:
                candidates.append(model)
        return candidates

    def _ensure_client(self) -> None:
        if self.client is not None:
            return

        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            logger.error(
                "OpenRouter authentication failed: OPENROUTER_API_KEY is not configured. "
                "Set a valid key in backend/.env to enable AI intake features."
            )
            raise OpenRouterAuthenticationError("OPENROUTER_API_KEY is not configured.")

        http_client = httpx.AsyncClient(proxies=settings.HTTP_PROXY, timeout=60.0)
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=settings.openrouter_api_key,
            max_retries=0,
            http_client=http_client,
            default_headers={
                "HTTP-Referer": settings.openrouter_http_referer,
                "X-Title": settings.openrouter_app_title,
            },
        )
        logger.info("OpenRouterService initialized base_url=%s", self.base_url)

    async def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
        """
        Call OpenRouter and return a parsed JSON dict.

        Tries response_format=json_object first per model; falls back to prompt-only
        JSON enforcement when the selected free model does not support structured output.
        """
        self._ensure_client()

        messages = [
            {"role": "system", "content": system_prompt + JSON_ONLY_SUFFIX},
            {"role": "user", "content": user_prompt},
        ]

        content: str | None = None
        last_error: Exception | None = None

        for model in self._model_candidates():
            for use_json_format in (True, False):
                try:
                    content = await self._complete(
                        messages,
                        model=model,
                        use_json_format=use_json_format,
                    )
                    if content and content.strip():
                        logger.info(
                            "OpenRouter success model=%s json_format=%s",
                            model,
                            use_json_format,
                        )
                        break
                except AuthenticationError as exc:
                    logger.error(
                        "OpenRouter authentication failed (401 Unauthorized): "
                        "invalid or missing API key. Check OPENROUTER_API_KEY in backend/.env. "
                        "Detail: %s",
                        exc,
                    )
                    raise OpenRouterAuthenticationError(
                        "OpenRouter authentication failed."
                    ) from exc
                except APIConnectionError as exc:
                    last_error = exc
                    logger.warning(
                        "OpenRouter API connection error (network timeout or unreachable) "
                        "model=%s json_format=%s: %s",
                        model,
                        use_json_format,
                        exc,
                    )
                except APIStatusError as exc:
                    if exc.status_code == 401:
                        logger.error(
                            "OpenRouter authentication failed (401 Unauthorized): "
                            "invalid API key. Check OPENROUTER_API_KEY in backend/.env. "
                            "model=%s json_format=%s status=%s",
                            model,
                            use_json_format,
                            exc.status_code,
                        )
                        raise OpenRouterAuthenticationError(
                            "OpenRouter authentication failed."
                        ) from exc
                    last_error = exc
                    logger.warning(
                        "OpenRouter API status error model=%s json_format=%s status=%s: %s",
                        model,
                        use_json_format,
                        exc.status_code,
                        exc,
                    )
                except RateLimitError as exc:
                    last_error = exc
                    logger.warning(
                        "OpenRouter rate limit exceeded model=%s json_format=%s: %s",
                        model,
                        use_json_format,
                        exc,
                    )
                except Exception as exc:
                    last_error = exc
                    logger.warning(
                        "OpenRouter call failed model=%s json_format=%s: %s",
                        model,
                        use_json_format,
                        exc,
                    )

            if content and content.strip():
                break

        if not content or not content.strip():
            if isinstance(last_error, (APIConnectionError, APIStatusError, RateLimitError)):
                raise OpenRouterServiceError(
                    f"OpenRouter API request failed: {last_error}"
                ) from last_error
            raise OpenRouterServiceError(
                "Empty response from OpenRouter after trying all configured models."
            )

        try:
            return parse_llm_json(content)
        except ValueError:
            try:
                return json.loads(content.strip())
            except json.JSONDecodeError as exc:
                raise OpenRouterServiceError(
                    "Failed to parse JSON from OpenRouter response."
                ) from exc

    async def _complete(
        self,
        messages: list[dict],
        *,
        model: str,
        use_json_format: bool,
    ) -> str:
        request_kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2000,
        }

        if use_json_format:
            request_kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content or ""


openrouter_service = OpenRouterService()
