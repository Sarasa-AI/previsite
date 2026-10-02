import json
import logging

from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from app.core.config import settings
from app.core.sentry import capture_categorized_error
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
        self.client: object | None = None
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

    async def _complete(
        self,
        messages: list[dict],
        *,
        model: str,
        use_json_format: bool,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        from app.privacy.llm_egress_gateway import LlmEgressError, chat_completion

        self._ensure_client()
        response_format = {"type": "json_object"} if use_json_format else None
        try:
            result = await chat_completion(
                base_url=self.base_url,
                api_key=settings.openrouter_api_key or "",
                model=model,
                messages=messages,
                purpose="openrouter_chat",
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except LlmEgressError as exc:
            raise OpenRouterServiceError(str(exc)) from exc
        return result.content

    def _ensure_client(self) -> None:
        """Validate API key; HTTP client lives in llm_egress_gateway only."""
        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            logger.error(
                "OpenRouter authentication failed: OPENROUTER_API_KEY is not configured. "
                "Set a valid key in backend/.env to enable AI intake features."
            )
            raise OpenRouterAuthenticationError("OPENROUTER_API_KEY is not configured.")
        # Mark ready without constructing the provider HTTP client here
        # (gateway owns clients).
        self.client = True  # type: ignore[assignment]

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
            err: Exception
            if isinstance(last_error, (APIConnectionError, APIStatusError, RateLimitError)):
                err = OpenRouterServiceError(
                    f"OpenRouter Tier 1 request failed: {last_error}"
                )
                err.__cause__ = last_error
            else:
                err = OpenRouterServiceError(
                    f"Empty response from OpenRouter Tier 1 model={primary_model}."
                )
            capture_categorized_error(
                err,
                category="llm",
                context={"provider": "openrouter", "tier": 1},
            )
            raise err

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


openrouter_service = OpenRouterService()
