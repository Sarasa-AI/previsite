import logging
import time
import asyncio
import httpx

from openai import APIConnectionError, APIStatusError, AuthenticationError, AsyncOpenAI, RateLimitError

from app.core.config import settings

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
        self.client = None
        self.model = settings.llm_model
        self._window_started_at = int(time.time())
        self._window_calls = 0
        self._total_calls = 0
        self._total_input_tokens = 0
        self._total_output_tokens = 0

        if self.provider != "openrouter":
            logger.error("Unsupported LLM provider configured: %s", self.provider)
            raise LLMServiceError(f"Unsupported LLM provider: {self.provider}")

    def _ensure_client(self) -> None:
        if self.client is not None:
            return

        if not settings.openrouter_api_key or not settings.openrouter_api_key.strip():
            raise LLMAuthenticationError("OPENROUTER_API_KEY is not configured.")

        http_client = httpx.AsyncClient(proxies=settings.HTTP_PROXY, timeout=60.0)

        self.client = AsyncOpenAI(
            base_url=settings.openrouter_base_url,
            api_key=settings.openrouter_api_key,
            max_retries=0,
            http_client=http_client,
            default_headers={
                "HTTP-Referer": settings.openrouter_http_referer,
                "X-Title": settings.openrouter_app_title,
            },
        )
        logger.info("LLMService initialized with OpenRouter model=%s", self.model)

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

    def get_system_prompt(self, current_data: str = "") -> str:
        return f"""شما یک دستیار پزشکی هوشمند و همدل هستید که در حال انجام مصاحبه با بیمار به زبان فارسی هستید.

هدف شما: جمع‌آوری تاریخچه پزشکی کامل بیمار به صورت گام‌به‌گام و محترمانه.

اطلاعاتی که تاکنون جمع‌آوری شده (فقط برای اطلاع شما):
{current_data}

دستورالعمل‌ها:
- فقط و فقط "یک" سوال در هر نوبت بپرسید.
- از پرسیدن سوالاتی که پاسخ آن‌ها قبلاً داده شده خودداری کنید.
- از زبان فارسی ساده، روان و محترمانه استفاده کنید.
- در صورت ابراز درد یا نگرانی، با بیمار همدلی کنید (مثلاً: "متاسفم که این درد را تجربه می‌کنید").
- سوالات را کوتاه و مستقیم نگه دارید.
- مراحل را به ترتیب زیر طی کنید:
  1. جزئیات شکایت اصلی (شروع، مدت، شدت، عوامل تشدید یا بهبود)
  2. علائم همراه
  3. سوابق پزشکی گذشته
  4. داروهای مصرفی و آلرژی‌ها
  5. سوابق خانوادگی و اجتماعی (سیگار، الکل، شغل)

- هرگاه تمام اطلاعات لازم را جمع‌آوری کردید، دقیقاً با این جمله گفتگو را تمام کنید: "ممنون از همکاری شما. اطلاعات کافی جمع‌آوری شد. subject object plan"
- پاسخ‌های شما نباید بیش از ۲ یا ۳ جمله باشد.
"""

    async def chat_json(self, messages: list[dict], system_prompt: str) -> str:
        """LLM call optimized for structured JSON output."""
        self._ensure_client()
        self._check_local_rate_limit()

        logger.info("AI JSON call started provider=%s messages=%s", self.provider, len(messages))

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                request_kwargs = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        *messages,
                    ],
                    "temperature": 0.2,
                    "max_tokens": 2000,
                }
                try:
                    response = await self.client.chat.completions.create(
                        **request_kwargs,
                        response_format={"type": "json_object"},
                    )
                except Exception:
                    response = await self.client.chat.completions.create(**request_kwargs)

                usage = response.usage
                self._record_usage(
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                )
                logger.info("AI JSON call completed provider=%s", self.provider)
                return response.choices[0].message.content

            except (APIConnectionError, APIStatusError, RateLimitError) as exc:
                if attempt < max_retries - 1:
                    logger.warning(
                        "LLM JSON call failed (attempt %s/%s): %s. Retrying...",
                        attempt + 1,
                        max_retries,
                        exc,
                    )
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise LLMServiceError(
                    f"{self.provider.capitalize()} JSON request failed after {max_retries} attempts."
                ) from exc
            except AuthenticationError as exc:
                raise LLMAuthenticationError(
                    f"{self.provider.capitalize()} authentication failed."
                ) from exc
            except Exception as exc:
                raise LLMServiceError(f"Unexpected error during LLM JSON call: {exc}") from exc

        raise LLMServiceError(f"Unsupported LLM provider: {self.provider}")

    async def chat(self, messages: list[dict], system_prompt: str = None) -> str:
        """
        messages format: [{"role": "user/assistant", "content": "..."}]
        """
        self._ensure_client()
        self._check_local_rate_limit()
        
        if not system_prompt:
            system_prompt = self.get_system_prompt()
            
        logger.info("AI call started provider=%s messages=%s", self.provider, len(messages))

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *messages
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                usage = response.usage
                self._record_usage(
                    input_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                    output_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                )
                logger.info("AI call completed provider=%s", self.provider)
                return response.choices[0].message.content

            except (APIConnectionError, APIStatusError, RateLimitError) as exc:
                if attempt < max_retries - 1:
                    logger.warning(f"LLM call failed (attempt {attempt+1}/{max_retries}): {exc}. Retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                raise LLMServiceError(f"{self.provider.capitalize()} service request failed after {max_retries} attempts.") from exc
            except AuthenticationError as exc:
                raise LLMAuthenticationError(f"{self.provider.capitalize()} authentication failed.") from exc
            except Exception as exc:
                raise LLMServiceError(f"Unexpected error during LLM call: {exc}") from exc

        raise LLMServiceError(f"Unsupported LLM provider: {self.provider}")

llm_service = LLMService()
