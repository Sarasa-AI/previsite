import logging

import httpx
import ollama
from openai import (
    APIConnectionError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    RateLimitError,
)

from app.core.config import settings
from app.services.openrouter_service import openrouter_service

logger = logging.getLogger(__name__)


class Tier2LLMError(Exception):
    """Raised when Tier 2 LLM call fails."""


class Tier2LLMClient:
    """Configurable secondary LLM provider (GapGPT, Ollama, or OpenRouter secondary)."""

    def __init__(self) -> None:
        self._openai_client: AsyncOpenAI | None = None
        self._ollama_client: ollama.AsyncClient | None = None

    @property
    def provider(self) -> str:
        return settings.llm_tier2_provider.strip().lower()

    def is_configured(self) -> bool:
        provider = self.provider
        if provider == "gapgpt":
            return bool(settings.gapgpt_api_key and settings.gapgpt_api_key.strip())
        if provider == "ollama":
            return bool(settings.ollama_host and settings.ollama_host.strip())
        if provider == "openrouter":
            return bool(
                settings.openrouter_api_key
                and settings.openrouter_api_key.strip()
                and settings.llm_tier2_openrouter_model.strip()
            )
        logger.warning("Unknown LLM_TIER2_PROVIDER=%r — Tier 2 unavailable", provider)
        return False

    def _ensure_openai_client(self, *, base_url: str, api_key: str) -> AsyncOpenAI:
        if self._openai_client is not None:
            return self._openai_client

        http_client_kwargs = {"timeout": 60.0}
        if settings.HTTP_PROXY and settings.HTTP_PROXY.strip():
            http_client_kwargs["proxies"] = settings.HTTP_PROXY
        http_client = httpx.AsyncClient(**http_client_kwargs)

        self._openai_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,
            http_client=http_client,
        )
        return self._openai_client

    def _ensure_ollama_client(self) -> ollama.AsyncClient:
        if self._ollama_client is None:
            self._ollama_client = ollama.AsyncClient(host=settings.ollama_host)
        return self._ollama_client

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
            if self.provider == "ollama":
                return await self._complete_ollama(
                    messages,
                    json_mode=json_mode,
                    temperature=temperature,
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
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
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
        client = self._ensure_openai_client(
            base_url=settings.gapgpt_base_url,
            api_key=settings.gapgpt_api_key or "",
        )
        request_kwargs: dict = {
            "model": settings.gapgpt_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            try:
                response = await client.chat.completions.create(
                    **request_kwargs,
                    response_format={"type": "json_object"},
                )
            except Exception:
                response = await client.chat.completions.create(**request_kwargs)
        else:
            response = await client.chat.completions.create(**request_kwargs)
        return response.choices[0].message.content or ""

    async def _complete_ollama(
        self,
        messages: list[dict],
        *,
        json_mode: bool,
        temperature: float,
    ) -> str:
        client = self._ensure_ollama_client()
        options: dict = {"temperature": temperature}
        if json_mode:
            options["format"] = "json"

        response = await client.chat(
            model=settings.llm_tier2_ollama_model,
            messages=messages,
            options=options,
        )
        return response.message.content or ""

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
