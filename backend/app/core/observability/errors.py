"""Structured pipeline failure diagnostics (never replaces raise/return paths)."""

from __future__ import annotations

from app.core.observability.telemetry import (
    build_pipeline_event,
    emit_pipeline_event,
)


def emit_pipeline_failure(
    *,
    module: str,
    stage: str,
    exc: BaseException,
    duration_ms: int,
    recoverable: bool,
    retryable: bool,
    session_id: int | None = None,
    patient_id: int | None = None,
) -> None:
    event = build_pipeline_event(
        module=module,
        pipeline_stage=stage,
        latency_ms=duration_ms,
        status="failure",
        session_id=session_id,
        patient_id=patient_id,
        error_type=type(exc).__name__,
        recoverable=recoverable,
        retryable=retryable,
    )
    emit_pipeline_event(event)
