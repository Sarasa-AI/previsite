"""Shared clinical pipeline telemetry contract (PHI-safe)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from app.core.observability.context import get_context, get_correlation_id, new_correlation_id
from app.core.observability.cost import estimate_cost_usd
from app.core.observability.metrics import observe_cost, observe_tokens

PipelineStatus = Literal["success", "failure"]

# Allowlisted keys that may appear in structured telemetry extras.
_ALLOWED_EXTRA_KEYS = frozenset(
    {
        "event",
        "timestamp",
        "correlation_id",
        "request_id",
        "session_id",
        "patient_id",
        "module",
        "pipeline_stage",
        "latency_ms",
        "status",
        "error_type",
        "recoverable",
        "retryable",
        "evidence_count",
        "lab_count",
        "medication_count",
        "pmh_count",
        "conflict_count",
        "confidence",
        "llm_model",
        "prompt_version",
        "completion_version",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
    }
)


class ClinicalPipelineEvent(BaseModel):
    """Base telemetry contract for every clinical pipeline stage/module."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["clinical_pipeline"] = "clinical_pipeline"
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    correlation_id: str
    request_id: str
    session_id: int | None = None
    patient_id: int | None = None
    module: str
    pipeline_stage: str
    latency_ms: int
    status: PipelineStatus
    error_type: str | None = None
    recoverable: bool | None = None
    retryable: bool | None = None
    evidence_count: int | None = None
    lab_count: int | None = None
    medication_count: int | None = None
    pmh_count: int | None = None
    conflict_count: int | None = None
    confidence: float | None = None


class AITelemetryEvent(ClinicalPipelineEvent):
    """LLM specialization of ClinicalPipelineEvent."""

    event: Literal["ai_telemetry"] = "ai_telemetry"
    llm_model: str | None = None
    prompt_version: str | None = None
    completion_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


def _resolve_ids(
    correlation_id: str | None,
    request_id: str | None,
) -> tuple[str, str]:
    ctx = get_context()
    cid = correlation_id or ctx.correlation_id or get_correlation_id() or new_correlation_id()
    rid = request_id or ctx.request_id or cid
    return cid, rid


def _phi_safe_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if k in _ALLOWED_EXTRA_KEYS and v is not None}


def emit_pipeline_event(event: ClinicalPipelineEvent) -> None:
    payload = _phi_safe_payload(event.model_dump())
    level = "ERROR" if event.status == "failure" else "INFO"
    logger.bind(**payload).log(level, event.event)


def emit_ai_telemetry(event: AITelemetryEvent) -> None:
    if event.estimated_cost_usd is None and event.llm_model:
        event = event.model_copy(
            update={
                "estimated_cost_usd": estimate_cost_usd(
                    event.llm_model,
                    event.input_tokens,
                    event.output_tokens,
                )
            }
        )
    observe_tokens(event.llm_model, event.input_tokens, event.output_tokens)
    observe_cost(event.llm_model, event.estimated_cost_usd)
    payload = _phi_safe_payload(event.model_dump())
    level = "ERROR" if event.status == "failure" else "INFO"
    logger.bind(**payload).log(level, event.event)


def build_pipeline_event(
    *,
    module: str,
    pipeline_stage: str,
    latency_ms: int,
    status: PipelineStatus,
    correlation_id: str | None = None,
    request_id: str | None = None,
    session_id: int | None = None,
    patient_id: int | None = None,
    error_type: str | None = None,
    recoverable: bool | None = None,
    retryable: bool | None = None,
    evidence_count: int | None = None,
    lab_count: int | None = None,
    medication_count: int | None = None,
    pmh_count: int | None = None,
    conflict_count: int | None = None,
    confidence: float | None = None,
) -> ClinicalPipelineEvent:
    ctx = get_context()
    cid, rid = _resolve_ids(correlation_id, request_id)
    return ClinicalPipelineEvent(
        correlation_id=cid,
        request_id=rid,
        session_id=session_id if session_id is not None else ctx.session_id,
        patient_id=patient_id if patient_id is not None else ctx.patient_id,
        module=module,
        pipeline_stage=pipeline_stage,
        latency_ms=latency_ms,
        status=status,
        error_type=error_type,
        recoverable=recoverable,
        retryable=retryable,
        evidence_count=evidence_count,
        lab_count=lab_count,
        medication_count=medication_count,
        pmh_count=pmh_count,
        conflict_count=conflict_count,
        confidence=confidence,
    )


def build_ai_telemetry_event(
    *,
    module: str,
    pipeline_stage: str,
    latency_ms: int,
    status: PipelineStatus,
    correlation_id: str | None = None,
    request_id: str | None = None,
    session_id: int | None = None,
    patient_id: int | None = None,
    error_type: str | None = None,
    recoverable: bool | None = None,
    retryable: bool | None = None,
    evidence_count: int | None = None,
    lab_count: int | None = None,
    medication_count: int | None = None,
    pmh_count: int | None = None,
    conflict_count: int | None = None,
    confidence: float | None = None,
    llm_model: str | None = None,
    prompt_version: str | None = None,
    completion_version: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
) -> AITelemetryEvent:
    base = build_pipeline_event(
        module=module,
        pipeline_stage=pipeline_stage,
        latency_ms=latency_ms,
        status=status,
        correlation_id=correlation_id,
        request_id=request_id,
        session_id=session_id,
        patient_id=patient_id,
        error_type=error_type,
        recoverable=recoverable,
        retryable=retryable,
        evidence_count=evidence_count,
        lab_count=lab_count,
        medication_count=medication_count,
        pmh_count=pmh_count,
        conflict_count=conflict_count,
        confidence=confidence,
    )
    return AITelemetryEvent(
        **base.model_dump(exclude={"event"}),
        llm_model=llm_model,
        prompt_version=prompt_version,
        completion_version=completion_version,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimated_cost_usd,
    )
