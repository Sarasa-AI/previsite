"""Immutable Inference Runtime domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.core.inference.domain.enums import InferenceStatus

# Domain schema version (independent of wire CONTRACT_VERSION).
INFERENCE_SCHEMA_VERSION = "1.0.0"


class InferenceRequest(BaseModel):
    """Immutable request descriptor submitted to the inference pipeline."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    session_id: int
    product_key: str
    context_reference: str
    requested_at: datetime

    @field_validator("execution_id")
    @classmethod
    def _non_empty_execution_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("execution_id must be non-empty")
        return stripped

    @field_validator("product_key")
    @classmethod
    def _non_empty_product_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("product_key must be non-empty")
        return stripped

    @field_validator("context_reference")
    @classmethod
    def _non_empty_context_reference(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("context_reference must be non-empty")
        return stripped

    @field_validator("session_id")
    @classmethod
    def _positive_session(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("session_id must be positive")
        return value

    @classmethod
    def create(
        cls,
        *,
        session_id: int,
        product_key: str,
        context_reference: str,
        execution_id: str | None = None,
        requested_at: datetime | None = None,
    ) -> InferenceRequest:
        """Factory for a new inference request."""
        return cls(
            execution_id=execution_id or str(uuid.uuid4()),
            session_id=session_id,
            product_key=product_key,
            context_reference=context_reference,
            requested_at=requested_at or datetime.now(timezone.utc),
        )


class InferenceFinding(BaseModel):
    """Neutral inference artifact — domain-agnostic, no Intelligence coupling."""

    model_config = ConfigDict(frozen=True)

    artifact_type: str
    finding_key: str
    title: str
    summary: str
    confidence: float | None = None
    attributes: dict[str, object] = {}

    @field_validator("artifact_type")
    @classmethod
    def _non_empty_artifact_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("artifact_type must be non-empty")
        return stripped

    @field_validator("finding_key")
    @classmethod
    def _non_empty_finding_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("finding_key must be non-empty")
        return stripped

    @field_validator("title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must be non-empty")
        return stripped

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not 0.0 <= value <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")
        return value


class ExecutionTrace(BaseModel):
    """Timing and provenance metadata for a completed inference execution."""

    model_config = ConfigDict(frozen=True)

    started_at: datetime
    finished_at: datetime
    adapter_name: str
    adapter_version: str
    runtime_version: str
    product_key: str

    @field_validator("adapter_name")
    @classmethod
    def _non_empty_adapter_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("adapter_name must be non-empty")
        return stripped

    @field_validator("adapter_version")
    @classmethod
    def _non_empty_adapter_version(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("adapter_version must be non-empty")
        return stripped

    @field_validator("product_key")
    @classmethod
    def _non_empty_product_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("product_key must be non-empty")
        return stripped


class InferenceResult(BaseModel):
    """Immutable result produced by an inference adapter."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    status: InferenceStatus
    findings: tuple[InferenceFinding, ...] = ()
    execution_trace: ExecutionTrace
    duration: float
    runtime_metadata: dict[str, str | int | float | bool | None] = {}

    @field_validator("execution_id")
    @classmethod
    def _non_empty_execution_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("execution_id must be non-empty")
        return stripped

    @field_validator("duration")
    @classmethod
    def _non_negative_duration(cls, value: float) -> float:
        if value < 0.0:
            raise ValueError("duration must be non-negative")
        return value


class InferenceExecution(BaseModel):
    """Lifecycle aggregate: tracks an inference from request through completion."""

    model_config = ConfigDict(frozen=True)

    request: InferenceRequest
    status: InferenceStatus
    result: InferenceResult | None = None

    @model_validator(mode="after")
    def _status_result_consistency(self) -> InferenceExecution:
        terminal = {InferenceStatus.SUCCEEDED, InferenceStatus.FAILED, InferenceStatus.SKIPPED}
        if self.status in terminal and self.result is None:
            raise ValueError(f"result must be set when status is {self.status}")
        if self.status not in terminal and self.result is not None:
            raise ValueError("result must be None for non-terminal status")
        return self

    @classmethod
    def create(cls, *, request: InferenceRequest) -> InferenceExecution:
        """Create a new execution in PENDING state."""
        return cls(request=request, status=InferenceStatus.PENDING, result=None)

    def mark_running(self) -> InferenceExecution:
        """Advance PENDING → RUNNING."""
        if self.status is not InferenceStatus.PENDING:
            raise ValueError(f"Can only mark PENDING execution as running; current: {self.status}")
        return InferenceExecution(request=self.request, status=InferenceStatus.RUNNING, result=None)

    def complete(self, result: InferenceResult) -> InferenceExecution:
        """Advance RUNNING → terminal status from result."""
        if self.status is not InferenceStatus.RUNNING:
            raise ValueError(f"Can only complete a RUNNING execution; current: {self.status}")
        terminal = {InferenceStatus.SUCCEEDED, InferenceStatus.FAILED, InferenceStatus.SKIPPED}
        if result.status not in terminal:
            raise ValueError(f"Result status must be terminal; got: {result.status}")
        return InferenceExecution(request=self.request, status=result.status, result=result)
