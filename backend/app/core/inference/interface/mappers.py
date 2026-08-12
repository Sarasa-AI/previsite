"""One-way domain → DTO mappers for Inference Runtime."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.inference.domain.models import (
    ExecutionTrace,
    InferenceFinding,
    InferenceResult,
)
from app.core.inference.interface.dto import (
    CONTRACT_VERSION,
    ExecutionTraceDTO,
    InferenceFindingDTO,
    InferenceResultDTO,
    InferenceResultResponse,
)


def format_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_finding_dto(finding: InferenceFinding) -> InferenceFindingDTO:
    return InferenceFindingDTO(
        artifact_type=finding.artifact_type,
        finding_key=finding.finding_key,
        title=finding.title,
        summary=finding.summary,
        confidence=finding.confidence,
        attributes=dict(finding.attributes),
    )


def to_trace_dto(trace: ExecutionTrace) -> ExecutionTraceDTO:
    return ExecutionTraceDTO(
        started_at=format_utc_z(trace.started_at),
        finished_at=format_utc_z(trace.finished_at),
        adapter_name=trace.adapter_name,
        adapter_version=trace.adapter_version,
        runtime_version=trace.runtime_version,
        product_key=trace.product_key,
    )


def to_result_dto(result: InferenceResult) -> InferenceResultDTO:
    return InferenceResultDTO(
        execution_id=result.execution_id,
        status=result.status.value,
        findings=[to_finding_dto(f) for f in result.findings],
        execution_trace=to_trace_dto(result.execution_trace),
        duration=result.duration,
        runtime_metadata=dict(result.runtime_metadata),
    )


def to_result_response(result: InferenceResult) -> InferenceResultResponse:
    return InferenceResultResponse(
        contract_version=CONTRACT_VERSION,
        result=to_result_dto(result),
    )
