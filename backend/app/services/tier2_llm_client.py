import logging

import httpx
from openai import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    RateLimitError,
)

from app.core.config import settings
from app.privacy.llm_egress_gateway import LlmEgressError, chat_completion
from app.services.openrouter_service import openrouter_service

logger = logging.getLogger(__name__)


class Tier2LLMError(Exception):
    """Raised when Tier 2 LLM call fails."""


class Tier2LLMClient:
    """Configurable secondary LLM provider (GapGPT or OpenRouter secondary)."""

    def __init__(self) -> None:
        pass

    @property
    def provider(self) -> str:
        return settings.llm_tier2_provider.strip().lower()

    def is_configured(self) -> bool:
        provider = self.provider
        if provider == "gapgpt":
            return bool(settings.gapgpt_api_key and settings.gapgpt_api_key.strip())
        if provider == "openrouter":
            return bool(
                settings.openrouter_api_key
                and settings.openrouter_api_key.strip()
                and settings.llm_tier2_openrouter_model.strip()
            )
        logger.warning("Unknown LLM_TIER2_PROVIDER=%r — Tier 2 unavailable", provider)
        return False

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> str:
        if not self.is_configured():
            raise Tier2LLMError(
                f"Tier 2 provider {self.provider!r} is not configured."
            )

        try:
            if self.provider == "gapgpt":
                return await self._complete_gapgpt(
                    messages,
                    json_mode=json_mode,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            if self.provider == "openrouter":
                return await self._complete_openrouter(
                    messages,
                    json_mode=json_mode,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise Tier2LLMError(f"Unsupported Tier 2 provider: {self.provider}")
        except Tier2LLMError:
            raise
        except (APIConnectionError, RateLimitError, APIStatusError, LlmEgressError) as exc:
            raise Tier2LLMError(str(exc)) from exc
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise Tier2LLMError(str(exc)) from exc
        except Exception as exc:
            raise Tier2LLMError(f"Unexpected Tier 2 error: {exc}") from exc

    async def _complete_gapgpt(
        self,
        messages: list[dict],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        response_format = {"type": "json_object"} if json_mode else None
        try:
            result = await chat_completion(
                base_url=settings.gapgpt_base_url,
                api_key=settings.gapgpt_api_key or "",
                model=settings.gapgpt_model,
                messages=messages,
                purpose="tier2_gapgpt",
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
            return result.content
        except LlmEgressError:
            if not json_mode:
                raise
            # Retry without json_object if unsupported.
            result = await chat_completion(
                base_url=settings.gapgpt_base_url,
                api_key=settings.gapgpt_api_key or "",
                model=settings.gapgpt_model,
                messages=messages,
                purpose="tier2_gapgpt",
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=None,
            )
            return result.content

    async def _complete_openrouter(
        self,
        messages: list[dict],
        *,
        json_mode: bool,
        temperature: float,
        max_tokens: int,
    ) -> str:
        openrouter_service._ensure_client()
        model = settings.llm_tier2_openrouter_model
        try:
            return await openrouter_service._complete(
                messages,
                model=model,
                use_json_format=json_mode,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AuthenticationError as exc:
            raise Tier2LLMError(f"OpenRouter Tier 2 authentication failed: {exc}") from exc


tier2_llm_client = Tier2LLMClient()
