import asyncio
import logging
import time
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class Tier1CircuitBreaker:
    """In-process circuit breaker for Tier 1 (OpenRouter primary) LLM calls."""

    def __init__(
        self,
        *,
        failure_threshold: int | None = None,
        cooldown_seconds: int | None = None,
    ) -> None:
        self._failure_threshold = (
            settings.llm_circuit_failure_threshold
            if failure_threshold is None
            else failure_threshold
        )
        self._cooldown_seconds = (
            settings.llm_circuit_cooldown_seconds
            if cooldown_seconds is None
            else cooldown_seconds
        )
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def should_skip_tier1(self) -> bool:
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return False

            if self._state == CircuitState.HALF_OPEN:
                logger.warning("Circuit breaker HALF_OPEN — probing Tier 1")
                return False

            if self._state == CircuitState.OPEN:
                if self._opened_at is None:
                    return True
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self._cooldown_seconds:
                    self._state = CircuitState.HALF_OPEN
                    logger.warning(
                        "Circuit breaker HALF_OPEN — cooldown elapsed (%ss), probing Tier 1",
                        self._cooldown_seconds,
                    )
                    return False
                logger.warning(
                    "Circuit breaker OPEN — skipping Tier 1, routing to Tier 2 "
                    "(cooldown remaining: %.0fs)",
                    self._cooldown_seconds - elapsed,
                )
                return True

            return False

    async def record_tier1_success(self) -> None:
        async with self._lock:
            if self._state in (CircuitState.OPEN, CircuitState.HALF_OPEN):
                logger.warning("Circuit breaker CLOSED — Tier 1 recovered")
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._opened_at = None

    async def record_tier1_failure(self, exc: Exception) -> None:
        async with self._lock:
            self._consecutive_failures += 1
            logger.warning(
                "Tier 1 LLM failed (%s/%s). Error: %s",
                self._consecutive_failures,
                self._failure_threshold,
                exc,
            )

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN — Tier 1 probe failed. Routing to Tier 2 for %ss.",
                    self._cooldown_seconds,
                )
                return

            if self._consecutive_failures >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker OPEN after %s consecutive Tier 1 failures. "
                    "Routing to Tier 2 for %ss.",
                    self._failure_threshold,
                    self._cooldown_seconds,
                )

    def reset(self) -> None:
        """Reset breaker state (primarily for tests)."""
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at = None


tier1_circuit_breaker = Tier1CircuitBreaker()
