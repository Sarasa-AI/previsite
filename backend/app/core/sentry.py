"""Optional Sentry integration — no-op when SENTRY_DSN is unset."""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

_sentry_initialized = False


def init_sentry() -> bool:
    """Initialize Sentry from settings. Returns True when active."""
    global _sentry_initialized
    if _sentry_initialized:
        return True

    from app.core.config import settings

    dsn = (settings.sentry_dsn or "").strip()
    if not dsn:
        logger.info("Sentry disabled (SENTRY_DSN not set)")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed; Sentry disabled")
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.app_env,
        traces_sample_rate=0.0,
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
    )
    _sentry_initialized = True
    logger.info("Sentry initialized environment=%s", settings.app_env)
    return True


def capture_categorized_error(
    exc: BaseException,
    *,
    category: str,
    context: Optional[dict[str, Any]] = None,
) -> None:
    """Send an error to Sentry with a category tag; never include raw PHI.

    Allowed context keys are numeric/session identifiers and non-PHI metadata
    (session_id, condition_id, mime_type, ocr_type, provider).
    """
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk
    except ImportError:
        return

    safe_context = {
        key: value
        for key, value in (context or {}).items()
        if key
        in {
            "session_id",
            "condition_id",
            "mime_type",
            "ocr_type",
            "provider",
            "path",
            "status_code",
            "tier",
        }
    }

    with sentry_sdk.push_scope() as scope:
        scope.set_tag("error_category", category)
        for key, value in safe_context.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(exc)
