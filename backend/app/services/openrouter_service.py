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
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "qwen/qwen-2.5-7b-instruct",
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

    def _model_candidates(self, models: list[str] | None = None) -> list[str]:
        if models:
            return models
        configured = settings.openrouter_default_model
        candidates = [configured]
        for model in FREE_MODEL_FALLBACKS:
            if model not in candidates:
                candidates.append(model)
        return candidates

    def intake_model_candidates(self) -> list[str]:
        """Fast Gemini-first model chain for latency-sensitive intake generation."""
        primary = settings.intake_llm_model.strip()
        candidates: list[str] = []
        for model in (primary, *FREE_MODEL_FALLBACKS):
            if model and model not in candidates:
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

        http_client_kwargs = {"timeout": 60.0}
        if settings.HTTP_PROXY and settings.HTTP_PROXY.strip():
            http_client_kwargs["proxies"] = settings.HTTP_PROXY
        http_client = httpx.AsyncClient(**http_client_kwargs)
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

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        models: list[str] | None = None,
        max_tokens: int = 2000,
    ) -> dict:
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

        for model in self._model_candidates(models):
            for use_json_format in (True, False):
                try:
                    content = await self._complete(
                        messages,
                        model=model,
                        use_json_format=use_json_format,
                        temperature=temperature,
                        max_tokens=max_tokens,
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

        return self._parse_json_content(content)

    async def generate_json_primary(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        model: str | None = None,
        max_tokens: int = 2000,
    ) -> dict:
        """Single-model Tier 1 call — no FREE_MODEL_FALLBACKS rotation."""
        self._ensure_client()

        primary_model = (model or settings.intake_llm_model).strip()
        messages = [
            {"role": "system", "content": system_prompt + JSON_ONLY_SUFFIX},
            {"role": "user", "content": user_prompt},
        ]

        content: str | None = None
        last_error: Exception | None = None

        for use_json_format in (True, False):
            try:
                content = await self._complete(
                    messages,
                    model=primary_model,
                    use_json_format=use_json_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if content and content.strip():
                    logger.info(
                        "OpenRouter Tier 1 success model=%s json_format=%s",
                        primary_model,
                        use_json_format,
                    )
                    break
            except AuthenticationError as exc:
                logger.error(
                    "OpenRouter authentication failed (401 Unauthorized): %s",
                    exc,
                )
                raise OpenRouterAuthenticationError(
                    "OpenRouter authentication failed."
                ) from exc
            except APIConnectionError as exc:
                last_error = exc
                logger.warning(
                    "OpenRouter Tier 1 connection error model=%s json_format=%s: %s",
                    primary_model,
                    use_json_format,
                    exc,
                )
            except APIStatusError as exc:
                if exc.status_code == 401:
                    raise OpenRouterAuthenticationError(
                        "OpenRouter authentication failed."
                    ) from exc
                last_error = exc
                logger.warning(
                    "OpenRouter Tier 1 status error model=%s status=%s: %s",
                    primary_model,
                    exc.status_code,
                    exc,
                )
            except RateLimitError as exc:
                last_error = exc
                logger.warning(
                    "OpenRouter Tier 1 rate limit model=%s: %s",
                    primary_model,
                    exc,
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "OpenRouter Tier 1 call failed model=%s json_format=%s: %s",
                    primary_model,
                    use_json_format,
                    exc,
                )

        if not content or not content.strip():
            if isinstance(last_error, (APIConnectionError, APIStatusError, RateLimitError)):
                raise OpenRouterServiceError(
                    f"OpenRouter Tier 1 request failed: {last_error}"
                ) from last_error
            raise OpenRouterServiceError(
                f"Empty response from OpenRouter Tier 1 model={primary_model}."
            )

        return self._parse_json_content(content)

    def _parse_json_content(self, content: str) -> dict:
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
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        request_kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if use_json_format:
            request_kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content or ""


openrouter_service = OpenRouterService()
