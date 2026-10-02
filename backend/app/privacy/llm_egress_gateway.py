"""Single egress gateway for external LLM / embedding / inference providers.

All outbound provider HTTP must go through this module. Direct AsyncOpenAI /
provider URL usage elsewhere is forbidden (enforced by codebase scan test).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.llm_egress_log import LlmEgressLog
from app.privacy.scrubber import (
    SCRUBBER_VERSION,
    PatientKnownIds,
    ScrubberError,
    messages_contain_image,
    rehydrate_text,
    scrub_messages,
    scrub_text,
)

logger = logging.getLogger(__name__)


class LlmEgressError(Exception):
    """Gateway-level refusal or transport failure."""


class LlmProviderNotAllowed(LlmEgressError):
    pass


class LlmImageEgressBlocked(LlmEgressError):
    pass


class LlmDeidentificationFailed(LlmEgressError):
    pass


@dataclass
class GatewayResult:
    content: str
    placeholders: dict[str, str] = field(default_factory=dict)
    replacement_counts: dict[str, int] = field(default_factory=dict)
    provider: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0

    def content_for_display(self) -> str:
        return rehydrate_text(self.content, self.placeholders)


@dataclass
class EmbedResult:
    embedding: list[float]
    replacement_counts: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0


def _allowlist_hosts() -> set[str]:
    raw = settings.external_llm_provider_allowlist or ""
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def _host_from_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return (parsed.hostname or "").lower()


def assert_provider_allowed(base_url: str) -> str:
    host = _host_from_url(base_url)
    allowed = _allowlist_hosts()
    if host not in allowed and not any(host.endswith("." + a) for a in allowed):
        raise LlmProviderNotAllowed(
            f"Provider host {host!r} is not on EXTERNAL_LLM_PROVIDER_ALLOWLIST"
        )
    return host


def _provider_label(base_url: str) -> str:
    host = _host_from_url(base_url)
    if "gapgpt" in host:
        return "gapgpt"
    if "openrouter" in host:
        return "openrouter"
    return host or "unknown"


_clients: dict[str, AsyncOpenAI] = {}


def _get_openai_client(*, base_url: str, api_key: str) -> AsyncOpenAI:
    assert_provider_allowed(base_url)
    key = f"{base_url}|{api_key[:8]}"
    if key in _clients:
        return _clients[key]
    http_kwargs: dict[str, Any] = {"timeout": 60.0}
    if settings.HTTP_PROXY and settings.HTTP_PROXY.strip():
        http_kwargs["proxies"] = settings.HTTP_PROXY
    http_client = httpx.AsyncClient(**http_kwargs)
    client = AsyncOpenAI(
        base_url=base_url,
        api_key=api_key,
        max_retries=0,
        http_client=http_client,
        default_headers={
            "HTTP-Referer": settings.openrouter_http_referer,
            "X-Title": settings.openrouter_app_title,
        },
    )
    _clients[key] = client
    return client


async def _write_egress_log(
    db: Optional[AsyncSession],
    *,
    session_id: Optional[int],
    user_id: Optional[int],
    provider: str,
    purpose: str,
    replacement_counts: dict[str, int],
    field_categories: list[str],
    response_status: str,
    latency_ms: float,
    usage: dict[str, int] | None = None,
) -> None:
    usage = usage or {}
    row = LlmEgressLog(
        session_id=session_id,
        user_id=user_id,
        provider=provider,
        purpose=purpose,
        scrubber_version=SCRUBBER_VERSION,
        replacement_counts=json.dumps(replacement_counts, ensure_ascii=False),
        field_categories=json.dumps(field_categories, ensure_ascii=False),
        response_status=response_status,
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
    )
    # Never store content — fields above are metadata only.
    if db is not None:
        try:
            db.add(row)
            await db.commit()
        except Exception:
            logger.exception("Failed to write llm_egress_log")
            try:
                await db.rollback()
            except Exception:
                pass
    else:
        # Best-effort: open a short-lived session when caller has no DB.
        try:
            from app.db.database import AsyncSessionLocal

            async with AsyncSessionLocal() as session:
                session.add(row)
                await session.commit()
        except Exception:
            logger.exception("Failed to write llm_egress_log (standalone)")


async def chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    purpose: str,
    temperature: float = 0.2,
    max_tokens: int = 2000,
    response_format: dict | None = None,
    known: PatientKnownIds | None = None,
    session_id: int | None = None,
    user_id: int | None = None,
    db: AsyncSession | None = None,
    rehydrate: bool = False,
) -> GatewayResult:
    """Scrub + allow-list + call provider chat completions."""
    provider = _provider_label(base_url)
    started = time.perf_counter()
    counts: dict[str, int] = {}
    placeholders: dict[str, str] = {}

    if messages_contain_image(messages) and not settings.allow_external_image_inference:
        await _write_egress_log(
            db,
            session_id=session_id,
            user_id=user_id,
            provider=provider,
            purpose=purpose,
            replacement_counts={},
            field_categories=["image_blocked"],
            response_status="blocked_image",
            latency_ms=0,
        )
        raise LlmImageEgressBlocked(
            "External image inference is disabled (ALLOW_EXTERNAL_IMAGE_INFERENCE=false)"
        )

    outbound = messages
    if settings.external_llm_deidentification_enabled:
        try:
            outbound, counts, placeholders = scrub_messages(messages, known=known)
        except ScrubberError as exc:
            await _write_egress_log(
                db,
                session_id=session_id,
                user_id=user_id,
                provider=provider,
                purpose=purpose,
                replacement_counts={},
                field_categories=["scrub_failed"],
                response_status="scrub_failed",
                latency_ms=0,
            )
            raise LlmDeidentificationFailed(str(exc)) from exc

    field_categories = sorted(counts.keys()) or ["text"]
    client = _get_openai_client(base_url=base_url, api_key=api_key)
    request_kwargs: dict[str, Any] = {
        "model": model,
        "messages": outbound,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format:
        request_kwargs["response_format"] = response_format

    try:
        response = await client.chat.completions.create(**request_kwargs)
        content = response.choices[0].message.content or ""
        usage_obj = getattr(response, "usage", None)
        usage = {}
        if usage_obj is not None:
            usage = {
                "prompt_tokens": getattr(usage_obj, "prompt_tokens", None) or 0,
                "completion_tokens": getattr(usage_obj, "completion_tokens", None) or 0,
                "total_tokens": getattr(usage_obj, "total_tokens", None) or 0,
            }
        status = "ok"
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        await _write_egress_log(
            db,
            session_id=session_id,
            user_id=user_id,
            provider=provider,
            purpose=purpose,
            replacement_counts=counts,
            field_categories=field_categories,
            response_status="error",
            latency_ms=latency,
        )
        raise LlmEgressError(str(exc)) from exc

    latency = (time.perf_counter() - started) * 1000
    await _write_egress_log(
        db,
        session_id=session_id,
        user_id=user_id,
        provider=provider,
        purpose=purpose,
        replacement_counts=counts,
        field_categories=field_categories,
        response_status=status,
        latency_ms=latency,
        usage=usage,
    )

    if rehydrate:
        content = rehydrate_text(content, placeholders)

    return GatewayResult(
        content=content,
        placeholders=placeholders,
        replacement_counts=counts,
        provider=provider,
        usage=usage,
        latency_ms=latency,
    )


async def embed(
    *,
    text: str,
    purpose: str = "embedding",
    known: PatientKnownIds | None = None,
    session_id: int | None = None,
    user_id: int | None = None,
    db: AsyncSession | None = None,
) -> EmbedResult:
    base_url = settings.openrouter_base_url
    provider = _provider_label(base_url)
    assert_provider_allowed(base_url)
    started = time.perf_counter()
    counts: dict[str, int] = {}

    outbound = text
    if settings.external_llm_deidentification_enabled:
        try:
            result = scrub_text(text, known=known)
            outbound = result.text
            counts = result.counts
        except ScrubberError as exc:
            await _write_egress_log(
                db,
                session_id=session_id,
                user_id=user_id,
                provider=provider,
                purpose=purpose,
                replacement_counts={},
                field_categories=["scrub_failed"],
                response_status="scrub_failed",
                latency_ms=0,
            )
            raise LlmDeidentificationFailed(str(exc)) from exc

    url = base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": settings.openrouter_http_referer,
        "X-Title": settings.openrouter_app_title,
    }
    payload = {
        "model": settings.openrouter_embedding_model,
        "input": outbound,
        "dimensions": settings.embedding_dimensions,
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            body = response.json()
        embedding = list(body["data"][0]["embedding"])
        status = "ok"
    except Exception as exc:
        latency = (time.perf_counter() - started) * 1000
        await _write_egress_log(
            db,
            session_id=session_id,
            user_id=user_id,
            provider=provider,
            purpose=purpose,
            replacement_counts=counts,
            field_categories=sorted(counts.keys()) or ["text"],
            response_status="error",
            latency_ms=latency,
        )
        raise LlmEgressError(str(exc)) from exc

    latency = (time.perf_counter() - started) * 1000
    await _write_egress_log(
        db,
        session_id=session_id,
        user_id=user_id,
        provider=provider,
        purpose=purpose,
        replacement_counts=counts,
        field_categories=sorted(counts.keys()) or ["text"],
        response_status=status,
        latency_ms=latency,
    )
    return EmbedResult(
        embedding=embedding, replacement_counts=counts, latency_ms=latency
    )


async def list_models(*, base_url: str, api_key: str, purpose: str = "health") -> Any:
    """Provider health probe (no patient payload)."""
    client = _get_openai_client(base_url=base_url, api_key=api_key)
    started = time.perf_counter()
    try:
        models = await client.models.list()
        status = "ok"
        result = models
    except Exception as exc:
        await _write_egress_log(
            None,
            session_id=None,
            user_id=None,
            provider=_provider_label(base_url),
            purpose=purpose,
            replacement_counts={},
            field_categories=[],
            response_status="error",
            latency_ms=(time.perf_counter() - started) * 1000,
        )
        raise LlmEgressError(str(exc)) from exc
    await _write_egress_log(
        None,
        session_id=None,
        user_id=None,
        provider=_provider_label(base_url),
        purpose=purpose,
        replacement_counts={},
        field_categories=[],
        response_status=status,
        latency_ms=(time.perf_counter() - started) * 1000,
    )
    return result
