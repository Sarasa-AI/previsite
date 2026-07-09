import json
import logging
import time

from openai import AuthenticationError

from app.core.config import settings
from app.services.llm_cascade import llm_cascade
from app.services.openrouter_service import OpenRouterAuthenticationError

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Base class for LLM service failures."""


class LLMAuthenticationError(LLMServiceError):
    """Raised when provider credentials are missing or invalid."""


class LLMRateLimitError(LLMServiceError):
    """Raised when provider or local rate limit is exceeded."""


class LLMService:
    def __init__(self):
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self._window_started_at = int(time.time())
        self._window_calls = 0
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        if self.provider != "openrouter":
            logger.error("Unsupported LLM provider configured: %s", self.provider)
            raise LLMServiceError(f"Unsupported LLM provider: {self.provider}")

    def _check_local_rate_limit(self) -> None:
        now = int(time.time())
        window = settings.llm_rate_limit_window_seconds
        limit = settings.llm_rate_limit_requests
        if now - self._window_started_at >= window:
            self._window_started_at = now
            self._window_calls = 0

        if self._window_calls >= limit:
            raise LLMRateLimitError(
                f"Local LLM rate limit exceeded ({limit} calls / {window}s)."
            )

        self._window_calls += 1

    def _record_usage(self, *, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self._total_calls += 1
        self._total_input_tokens += max(0, input_tokens)
        self._total_output_tokens += max(0, output_tokens)
        logger.info(
            "LLM usage calls=%s input_tokens=%s output_tokens=%s",
            self._total_calls,
            self._total_input_tokens,
            self._total_output_tokens,
        )

    def get_system_prompt(
        self,
        current_data: str = "",
        chat_history: list[dict] | None = None,
        stage_instruction: str = "",
    ) -> str:
        from app.services.intake_llm import build_interview_system_prompt

        return build_interview_system_prompt(
            clinical_context=current_data,
            chat_history=chat_history,
            stage_instruction=stage_instruction,
        )

    async def chat_json(
        self,
        messages: list[dict],
        system_prompt: str,
        *,
        tier3_factory=None,
    ) -> str:
        """LLM call optimized for structured JSON output via cascade."""
        self._check_local_rate_limit()

        logger.info("AI JSON call started provider=%s messages=%s", self.provider, len(messages))

        user_content = messages[-1]["content"] if messages else ""
        if tier3_factory is None:
            def _default_tier3() -> dict:
                raise LLMServiceError("No Tier 3 fallback configured for chat_json.")

            tier3 = _default_tier3
        else:
            tier3 = tier3_factory

        try:
            result = await llm_cascade.generate_json_with_cascade(
                system_prompt=system_prompt,
                user_prompt=user_content,
                tier3_factory=tier3,
                temperature=0.2,
                max_tokens=2000,
                tier1_model=self.model,
            )
            self._record_usage()
            logger.info(
                "AI JSON call completed provider=%s tier=%s fallback=%s",
                self.provider,
                result.tier_used,
                result.llm_fallback_used,
            )
            return json.dumps(result.data, ensure_ascii=False)
        except OpenRouterAuthenticationError as exc:
            raise LLMAuthenticationError(
                f"{self.provider.capitalize()} authentication failed."
            ) from exc
        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                f"{self.provider.capitalize()} authentication failed."
            ) from exc

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        *,
        tier3_factory=None,
    ) -> str:
        """
        messages format: [{"role": "user/assistant", "content": "..."}]
        """
        self._check_local_rate_limit()

        if not system_prompt:
            system_prompt = self.get_system_prompt()

        logger.info("AI call started provider=%s messages=%s", self.provider, len(messages))

        if tier3_factory is None:
            def _default_tier3() -> str:
                raise LLMServiceError("No Tier 3 fallback configured for chat.")

            tier3 = _default_tier3
        else:
            tier3 = tier3_factory

        try:
            result = await llm_cascade.chat_with_cascade(
                messages,
                system_prompt,
                tier3_factory=tier3,
                temperature=0.7,
                max_tokens=500,
                tier1_model=self.model,
            )
            self._record_usage()
            logger.info(
                "AI call completed provider=%s tier=%s fallback=%s",
                self.provider,
                result.tier_used,
                result.llm_fallback_used,
            )
            return result.data
        except OpenRouterAuthenticationError as exc:
            raise LLMAuthenticationError(
                f"{self.provider.capitalize()} authentication failed."
            ) from exc
        except AuthenticationError as exc:
            raise LLMAuthenticationError(
                f"{self.provider.capitalize()} authentication failed."
            ) from exc


llm_service = LLMService()
