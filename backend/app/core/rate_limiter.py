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
