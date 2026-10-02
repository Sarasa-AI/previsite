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


def _raise_rate_limited() -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please retry later.",
    )


def make_user_rate_limit(*, key_prefix: str, limit_attr: str, window_attr: str):
    """Build a FastAPI dependency that rate-limits by authenticated user id."""

    def _dependency(
        request: Request,
        current_user: User = Depends(get_current_user),
    ) -> None:
        limit = int(getattr(settings, limit_attr))
        window = int(getattr(settings, window_attr))
        user_key = getattr(current_user, "id", None)
        if user_key is None:
            user_key = "anon"
        key = f"{key_prefix}:{user_key}:{request.url.path}"
        if not rate_limiter.allow(key=key, limit=limit, window_seconds=window):
            _raise_rate_limited()

    return _dependency


chat_rate_limit = make_user_rate_limit(
    key_prefix="chat",
    limit_attr="chat_rate_limit_requests",
    window_attr="chat_rate_limit_window_seconds",
)
intake_write_rate_limit = make_user_rate_limit(
    key_prefix="intake_write",
    limit_attr="intake_write_rate_limit_requests",
    window_attr="intake_write_rate_limit_window_seconds",
)
file_upload_rate_limit = make_user_rate_limit(
    key_prefix="file_upload",
    limit_attr="file_upload_rate_limit_requests",
    window_attr="file_upload_rate_limit_window_seconds",
)
pdf_export_rate_limit = make_user_rate_limit(
    key_prefix="pdf_export",
    limit_attr="pdf_export_rate_limit_requests",
    window_attr="pdf_export_rate_limit_window_seconds",
)
ocr_read_rate_limit = make_user_rate_limit(
    key_prefix="ocr_read",
    limit_attr="ocr_read_rate_limit_requests",
    window_attr="ocr_read_rate_limit_window_seconds",
)
medications_search_rate_limit = make_user_rate_limit(
    key_prefix="med_search",
    limit_attr="medications_search_rate_limit_requests",
    window_attr="medications_search_rate_limit_window_seconds",
)
privacy_export_rate_limit = make_user_rate_limit(
    key_prefix="privacy_export",
    limit_attr="privacy_export_rate_limit_requests",
    window_attr="privacy_export_rate_limit_window_seconds",
)


def mfa_verify_rate_limit(request: Request) -> None:
    """Rate-limit MFA verify attempts separately from login lockout.

    Keyed by client IP plus a coarse token fingerprint (not the secret itself).
    """
    ip = request.client.host if request.client else "unknown"
    # Prefer body-derived identity is unavailable at dependency time without
    # consuming the body; IP + path is sufficient for abuse throttling.
    key = f"mfa_verify:{(ip or 'unknown').strip()}:{request.url.path}"
    if not rate_limiter.allow(
        key=key,
        limit=settings.mfa_verify_rate_limit_requests,
        window_seconds=settings.mfa_verify_rate_limit_window_seconds,
    ):
        _raise_rate_limited()


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
