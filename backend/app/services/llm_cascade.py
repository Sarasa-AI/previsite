import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx
from openai import APIConnectionError, APIStatusError, RateLimitError

from app.core.config import settings
from app.services.json_parser import parse_llm_json
from app.services.llm_circuit_breaker import tier1_circuit_breaker
from app.services.openrouter_service import (
    JSON_ONLY_SUFFIX,
    OpenRouterAuthenticationError,
    OpenRouterServiceError,
    openrouter_service,
)
from app.services.tier2_llm_client import Tier2LLMError, tier2_llm_client

logger = logging.getLogger(__name__)

RECOVERABLE_ERRORS = (
    APIConnectionError,
    APIStatusError,
    RateLimitError,
    TimeoutError,
    asyncio.TimeoutError,
    httpx.TimeoutException,
    OpenRouterServiceError,
    Tier2LLMError,
    ValueError,
)


@dataclass
class CascadeResult:
    data: Any
    tier_used: int
    llm_fallback_used: bool
    error_message: str | None = None


class LLMCascade:
    def __init__(self) -> None:
        self._timeout = settings.intake_llm_timeout_seconds

    def _classify_error(self, exc: Exception) -> str:
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
            return f"Timeout: LLM response exceeded {self._timeout:g}s SLA"
        message = str(exc).strip() or type(exc).__name__
        return message

    def _build_json_messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt + JSON_ONLY_SUFFIX},
            {"role": "user", "content": user_prompt},
        ]

    async def _try_tier1_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        model: str | None = None,
    ) -> dict:
        return await asyncio.wait_for(
            openrouter_service.generate_json_primary(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                model=model,
                max_tokens=max_tokens,
            ),
            timeout=self._timeout,
        )

    async def _try_tier2_json(
        self,
        messages: list[dict],
        *,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        content = await asyncio.wait_for(
            tier2_llm_client.complete(
                messages,
                json_mode=True,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self._timeout,
        )
        return parse_llm_json(content)

    async def _try_tier1_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
        model: str | None = None,
    ) -> str:
        openrouter_service._ensure_client()
        primary_model = (model or settings.llm_model).strip()
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        content = await asyncio.wait_for(
            openrouter_service._complete(
                full_messages,
                model=primary_model,
                use_json_format=False,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self._timeout,
        )
        if not content or not content.strip():
            raise OpenRouterServiceError("Empty response from Tier 1 chat.")
        return content

    async def _try_tier2_chat(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        full_messages = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]
        content = await asyncio.wait_for(
            tier2_llm_client.complete(
                full_messages,
                json_mode=False,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self._timeout,
        )
        if not content or not content.strip():
            raise Tier2LLMError("Empty response from Tier 2 chat.")
        return content

    async def generate_json_with_cascade(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        tier3_factory: Callable[[], dict],
        temperature: float = 0.2,
        max_tokens: int = 2000,
        tier1_model: str | None = None,
    ) -> CascadeResult:
        tier1_error: Exception | None = None
        tier2_error: Exception | None = None
        messages = self._build_json_messages(system_prompt, user_prompt)

        skip_tier1 = await tier1_circuit_breaker.should_skip_tier1()
        if not skip_tier1:
            try:
                data = await self._try_tier1_json(
                    system_prompt,
                    user_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=tier1_model,
                )
                await tier1_circuit_breaker.record_tier1_success()
                return CascadeResult(data=data, tier_used=1, llm_fallback_used=False)
            except OpenRouterAuthenticationError:
                raise
            except RECOVERABLE_ERRORS as exc:
                tier1_error = exc
                await tier1_circuit_breaker.record_tier1_failure(exc)
                logger.warning(
                    "Tier 1 LLM failed. Switching to Tier 2. Error: %s",
                    exc,
                )

        try:
            data = await self._try_tier2_json(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            error_message = self._classify_error(tier1_error) if tier1_error else None
            return CascadeResult(
                data=data,
                tier_used=2,
                llm_fallback_used=True,
                error_message=error_message,
            )
        except RECOVERABLE_ERRORS as exc:
            tier2_error = exc
            logger.warning(
                "Tier 2 LLM failed. Switching to Tier 3 static fallback. Error: %s",
                exc,
            )

        data = tier3_factory()
        errors = [e for e in (tier1_error, tier2_error) if e is not None]
        error_message = self._classify_error(errors[0]) if errors else None
        return CascadeResult(
            data=data,
            tier_used=3,
            llm_fallback_used=True,
            error_message=error_message,
        )

    async def chat_with_cascade(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        tier3_factory: Callable[[], str],
        temperature: float = 0.7,
        max_tokens: int = 500,
        tier1_model: str | None = None,
    ) -> CascadeResult:
        tier1_error: Exception | None = None
        tier2_error: Exception | None = None

        skip_tier1 = await tier1_circuit_breaker.should_skip_tier1()
        if not skip_tier1:
            try:
                content = await self._try_tier1_chat(
                    messages,
                    system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    model=tier1_model,
                )
                await tier1_circuit_breaker.record_tier1_success()
                return CascadeResult(
                    data=content,
                    tier_used=1,
                    llm_fallback_used=False,
                )
            except OpenRouterAuthenticationError:
                raise
            except RECOVERABLE_ERRORS as exc:
                tier1_error = exc
                await tier1_circuit_breaker.record_tier1_failure(exc)
                logger.warning(
                    "Tier 1 LLM failed. Switching to Tier 2. Error: %s",
                    exc,
                )

        try:
            content = await self._try_tier2_chat(
                messages,
                system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            error_message = self._classify_error(tier1_error) if tier1_error else None
            return CascadeResult(
                data=content,
                tier_used=2,
                llm_fallback_used=True,
                error_message=error_message,
            )
        except RECOVERABLE_ERRORS as exc:
            tier2_error = exc
            logger.warning(
                "Tier 2 LLM failed. Switching to Tier 3 static fallback. Error: %s",
                exc,
            )

        content = tier3_factory()
        errors = [e for e in (tier1_error, tier2_error) if e is not None]
        error_message = self._classify_error(errors[0]) if errors else None
        return CascadeResult(
            data=content,
            tier_used=3,
            llm_fallback_used=True,
            error_message=error_message,
        )


llm_cascade = LLMCascade()
