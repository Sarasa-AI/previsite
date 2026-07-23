import time
from collections import defaultdict, deque
from threading import Lock
from typing import Deque

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.models import User


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._store: dict[str, Deque[float]] = defaultdict(deque)
        self._lockouts: dict[str, float] = {}
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._store[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                return False

            bucket.append(now)
            return True

    def is_locked(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            until = self._lockouts.get(key)
            if until is None:
                return False
            if until <= now:
                del self._lockouts[key]
                self._store.pop(key, None)
                return False
            return True

    def lockout_remaining_seconds(self, key: str) -> int:
        now = time.time()
        with self._lock:
            until = self._lockouts.get(key)
            if until is None or until <= now:
                return 0
            return max(1, int(until - now))

    def record_failure(
        self,
        key: str,
        *,
        max_failures: int,
        window_seconds: int,
        lockout_seconds: int,
    ) -> tuple[int, bool]:
        """Record a failed attempt. Returns (failure_count, newly_locked)."""
        now = time.time()
        cutoff = now - window_seconds
        newly_locked = False

        with self._lock:
            bucket = self._store[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            bucket.append(now)
            count = len(bucket)
            if count >= max_failures:
                existing = self._lockouts.get(key)
                if existing is None or existing <= now:
                    self._lockouts[key] = now + lockout_seconds
                    newly_locked = True
            return count, newly_locked

    def clear(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._lockouts.pop(key, None)

    def reset(self) -> None:
        """Clear all buckets/lockouts (for tests)."""
        with self._lock:
            self._store.clear()
            self._lockouts.clear()


rate_limiter = InMemoryRateLimiter()


def chat_rate_limit(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> None:
    key = f"chat:{current_user.id}:{request.url.path}"
    if not rate_limiter.allow(
        key=key,
        limit=settings.chat_rate_limit_requests,
        window_seconds=settings.chat_rate_limit_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry in a minute.",
        )


def login_attempt_key(ip: str | None, login_id: str) -> str:
    normalized = (login_id or "").strip().lower()
    return f"auth:login:{(ip or 'unknown').strip()}:{normalized}"


def register_attempt_key(ip: str | None) -> str:
    return f"auth:register:{(ip or 'unknown').strip()}"


def raise_login_lockout(key: str) -> None:
    remaining = rate_limiter.lockout_remaining_seconds(key)
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Too many failed login attempts. Account login temporarily locked. "
            f"Try again in {remaining} seconds."
        ),
        headers={"Retry-After": str(remaining)},
    )
