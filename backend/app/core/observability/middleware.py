"""HTTP correlation middleware for end-to-end pipeline traceability."""

from __future__ import annotations

import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability.context import (
    bind,
    clear,
    new_correlation_id,
)

CORRELATION_HEADER = "X-Request-ID"
CORRELATION_HEADER_ALT = "X-Correlation-ID"


def resolve_incoming_correlation_id(request: Request) -> str:
    header = (
        request.headers.get(CORRELATION_HEADER)
        or request.headers.get(CORRELATION_HEADER_ALT)
        or ""
    ).strip()
    return header or new_correlation_id()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = resolve_incoming_correlation_id(request)
        bind(correlation_id=correlation_id, request_id=correlation_id)
        request.state.correlation_id = correlation_id

        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.bind(
                correlation_id=correlation_id,
                request_id=correlation_id,
                pipeline_stage="http.request",
            ).exception(
                "Request failed method={} path={} client_ip={} duration_ms={}",
                request.method,
                request.url.path,
                client_ip,
                duration_ms,
            )
            clear()
            raise

        duration_ms = int((time.perf_counter() - start) * 1000)
        response.headers[CORRELATION_HEADER] = correlation_id
        logger.bind(
            correlation_id=correlation_id,
            request_id=correlation_id,
            pipeline_stage="http.request",
        ).info(
            "HTTP {} {} client_ip={} status={} duration_ms={}",
            request.method,
            request.url.path,
            client_ip,
            response.status_code,
            duration_ms,
        )
        # Do not clear here: FastAPI BackgroundTasks may still run in this context.
        # Background workers that need isolation must re-bind explicitly.
        return response
