"""SMS provider interface and adapters (console / test / unimplemented HTTP)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.config import is_production_env, settings
from app.utils.phone import mask_phone_for_log

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmsResult:
    success: bool
    provider: str
    message_id: str | None = None
    error: str | None = None


class SmsProvider(Protocol):
    def send(
        self,
        phone: str,
        template_key: str,
        params: dict[str, Any],
    ) -> SmsResult: ...


class ConsoleSmsProvider:
    """Local-dev provider: logs a masked message; never logs the OTP code."""

    def __init__(self) -> None:
        if is_production_env():
            raise RuntimeError(
                "ConsoleSmsProvider must not be used when APP_ENV=production"
            )

    def send(
        self,
        phone: str,
        template_key: str,
        params: dict[str, Any],
    ) -> SmsResult:
        # Intentionally omit params (may contain code) from the log line.
        logger.info(
            "ConsoleSmsProvider: template=%s phone=%s (code omitted from logs)",
            template_key,
            mask_phone_for_log(phone),
        )
        return SmsResult(success=True, provider="console", message_id="console")


@dataclass
class TestSmsProvider:
    """In-memory outbox for tests. Codes are readable only via ``outbox``."""

    outbox: list[dict[str, Any]] = field(default_factory=list)

    def send(
        self,
        phone: str,
        template_key: str,
        params: dict[str, Any],
    ) -> SmsResult:
        self.outbox.append(
            {
                "phone": phone,
                "template_key": template_key,
                "params": dict(params),
            }
        )
        return SmsResult(
            success=True,
            provider="test",
            message_id=f"test-{len(self.outbox)}",
        )

    def clear(self) -> None:
        self.outbox.clear()

    def last_code_for(self, phone: str) -> str | None:
        for item in reversed(self.outbox):
            if item.get("phone") == phone:
                code = (item.get("params") or {}).get("code")
                return str(code) if code is not None else None
        return None


class HttpSmsProvider:
    """UNIMPLEMENTED — real SMS HTTP adapter slot for a future provider.

    Do not call in production until a real integration is shipped.
    """

    def send(
        self,
        phone: str,
        template_key: str,
        params: dict[str, Any],
    ) -> SmsResult:
        raise NotImplementedError(
            "HttpSmsProvider is not implemented. Configure a real SMS provider "
            "integration before using SMS_PROVIDER=http."
        )


_test_provider_singleton: TestSmsProvider | None = None


def get_test_sms_provider() -> TestSmsProvider:
    global _test_provider_singleton
    if _test_provider_singleton is None:
        _test_provider_singleton = TestSmsProvider()
    return _test_provider_singleton


def reset_test_sms_provider() -> None:
    global _test_provider_singleton
    if _test_provider_singleton is not None:
        _test_provider_singleton.clear()
    _test_provider_singleton = TestSmsProvider()


def get_sms_provider() -> SmsProvider:
    name = (settings.sms_provider or "console").strip().lower()
    if name == "console":
        return ConsoleSmsProvider()
    if name == "test":
        return get_test_sms_provider()
    if name == "http":
        return HttpSmsProvider()
    raise RuntimeError(f"Unknown SMS_PROVIDER={name!r}")
