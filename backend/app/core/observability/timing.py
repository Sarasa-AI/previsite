"""Stage timing context managers for the clinical pipeline."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any

from app.core.observability.context import bind
from app.core.observability.errors import emit_pipeline_failure
from app.core.observability.metrics import observe_duration, observe_ocr_duration
from app.core.observability.telemetry import build_pipeline_event, emit_pipeline_event


@dataclass
class StageResult:
    stage: str
    module: str
    latency_ms: int = 0
    status: str = "success"
    error_type: str | None = None
    attrs: dict[str, Any] = field(default_factory=dict)


@asynccontextmanager
async def pipeline_stage(
    stage: str,
    *,
    module: str,
    emit_event: bool = True,
    recoverable_on_error: bool = False,
    retryable_on_error: bool = False,
    ocr_type: str | None = None,
    **counts: Any,
) -> AsyncIterator[StageResult]:
    """Time an async pipeline stage and emit ClinicalPipelineEvent + metrics."""
    bind(pipeline_stage=stage, module=module)
    result = StageResult(stage=stage, module=module, attrs=dict(counts))
    start = time.perf_counter()
    try:
        yield result
        result.status = "success"
    except Exception as exc:
        result.status = "failure"
        result.error_type = type(exc).__name__
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        emit_pipeline_failure(
            module=module,
            stage=stage,
            exc=exc,
            duration_ms=result.latency_ms,
            recoverable=recoverable_on_error,
            retryable=retryable_on_error,
            session_id=counts.get("session_id"),
            patient_id=counts.get("patient_id"),
        )
        observe_duration(stage, result.latency_ms, "failure")
        if ocr_type is not None:
            observe_ocr_duration(result.latency_ms, "failure", ocr_type)
        raise
    else:
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        observe_duration(stage, result.latency_ms, "success")
        if ocr_type is not None:
            observe_ocr_duration(result.latency_ms, "success", ocr_type)
        if emit_event:
            event = build_pipeline_event(
                module=module,
                pipeline_stage=stage,
                latency_ms=result.latency_ms,
                status="success",
                evidence_count=result.attrs.get("evidence_count", counts.get("evidence_count")),
                lab_count=result.attrs.get("lab_count", counts.get("lab_count")),
                medication_count=result.attrs.get(
                    "medication_count", counts.get("medication_count")
                ),
                pmh_count=result.attrs.get("pmh_count", counts.get("pmh_count")),
                conflict_count=result.attrs.get("conflict_count", counts.get("conflict_count")),
                confidence=result.attrs.get("confidence", counts.get("confidence")),
                session_id=counts.get("session_id"),
                patient_id=counts.get("patient_id"),
            )
            emit_pipeline_event(event)


@contextmanager
def pipeline_stage_sync(
    stage: str,
    *,
    module: str,
    emit_event: bool = True,
    recoverable_on_error: bool = False,
    retryable_on_error: bool = False,
    ocr_type: str | None = None,
    **counts: Any,
) -> Iterator[StageResult]:
    """Sync variant for OCR and other sync call sites."""
    bind(pipeline_stage=stage, module=module)
    result = StageResult(stage=stage, module=module, attrs=dict(counts))
    start = time.perf_counter()
    try:
        yield result
        result.status = "success"
    except Exception as exc:
        result.status = "failure"
        result.error_type = type(exc).__name__
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        emit_pipeline_failure(
            module=module,
            stage=stage,
            exc=exc,
            duration_ms=result.latency_ms,
            recoverable=recoverable_on_error,
            retryable=retryable_on_error,
            session_id=counts.get("session_id"),
            patient_id=counts.get("patient_id"),
        )
        observe_duration(stage, result.latency_ms, "failure")
        if ocr_type is not None:
            observe_ocr_duration(result.latency_ms, "failure", ocr_type)
        raise
    else:
        result.latency_ms = int((time.perf_counter() - start) * 1000)
        observe_duration(stage, result.latency_ms, "success")
        if ocr_type is not None:
            observe_ocr_duration(result.latency_ms, "success", ocr_type)
        if emit_event:
            event = build_pipeline_event(
                module=module,
                pipeline_stage=stage,
                latency_ms=result.latency_ms,
                status="success",
                evidence_count=result.attrs.get("evidence_count", counts.get("evidence_count")),
                lab_count=result.attrs.get("lab_count", counts.get("lab_count")),
                medication_count=result.attrs.get(
                    "medication_count", counts.get("medication_count")
                ),
                pmh_count=result.attrs.get("pmh_count", counts.get("pmh_count")),
                conflict_count=result.attrs.get("conflict_count", counts.get("conflict_count")),
                confidence=result.attrs.get("confidence", counts.get("confidence")),
                session_id=counts.get("session_id"),
                patient_id=counts.get("patient_id"),
            )
            emit_pipeline_event(event)
