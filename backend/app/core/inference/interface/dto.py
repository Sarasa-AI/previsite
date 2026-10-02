"""Wire DTOs for Inference Runtime — no domain enums, no business behaviour."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Wire contract version (independent of INFERENCE_SCHEMA_VERSION).
CONTRACT_VERSION = "1.0.0"


class InferenceFindingDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_type: str
    finding_key: str
    title: str
    summary: str
    confidence: float | None = None
    attributes: dict[str, object] = Field(default_factory=dict)


class ExecutionTraceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    started_at: str
    finished_at: str
    adapter_name: str
    adapter_version: str
    runtime_version: str
    product_key: str


class InferenceResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    status: str
    findings: list[InferenceFindingDTO] = Field(default_factory=list)
    execution_trace: ExecutionTraceDTO
    duration: float
    runtime_metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict
    )


class InferenceResultResponse(BaseModel):
    """Versioned envelope for a single inference result."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = CONTRACT_VERSION
    result: InferenceResultDTO
