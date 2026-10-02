"""Wire DTOs for Doctor Workspace API — no domain enums, no business behavior."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Wire contract version (independent of orchestration algorithm version).
CONTRACT_VERSION = "1.0.0"


class TrustDescriptorDTO(BaseModel):
    """Wire projection of TrustDescriptor."""

    model_config = ConfigDict(frozen=True)

    primary_provenance: str
    all_provenance: list[str] = Field(default_factory=list)
    confidence: float | None = None
    verification: str
    evidence_refs: list[str] = Field(default_factory=list)


class LayoutDirectiveDTO(BaseModel):
    """Wire projection of LayoutDirective."""

    model_config = ConfigDict(frozen=True)

    object_id: str
    priority: str
    slot: str
    size: str
    pinned: bool
    trust: TrustDescriptorDTO
    flags: list[str] = Field(default_factory=list)
    visibility_reason: str | None = None


class DecisionQueueItemDTO(BaseModel):
    """Wire projection of DecisionQueueItem."""

    model_config = ConfigDict(frozen=True)

    rank: int
    object_id: str
    reason_code: str
    explanation: str
    acknowledge_required: bool


class CognitiveBudgetDTO(BaseModel):
    """Wire projection of CognitiveBudget."""

    model_config = ConfigDict(frozen=True)

    primary_count: int
    expanded_count: int
    deferred_count: int


class ClinicalStoryDTO(BaseModel):
    """Wire projection of ClinicalStory."""

    model_config = ConfigDict(frozen=True)

    text: str
    confidence: float | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    stale: bool = False


class PlanMetadataDTO(BaseModel):
    """Wire projection of WorkspacePlanMetadata."""

    model_config = ConfigDict(frozen=True)

    context_hash: str
    lens: str
    role: str
    computed_at: str
    workspace_plan_version: str
    generated_at: str
    generated_by: str
    compute_duration_ms: int


class WorkspacePlanResponse(BaseModel):
    """Top-level wire contract for plan endpoints (no decision_trace)."""

    model_config = ConfigDict(frozen=True)

    contract_version: str
    session_id: int
    workspace_state: str
    layout_directives: list[LayoutDirectiveDTO] = Field(default_factory=list)
    decision_queue: list[DecisionQueueItemDTO] = Field(default_factory=list)
    story: ClinicalStoryDTO | None = None
    pin_zone: list[str] = Field(default_factory=list)
    cognitive_budget: CognitiveBudgetDTO
    metadata: PlanMetadataDTO
    plan_etag: str


class AcknowledgementRequest(BaseModel):
    """Request body for P0 acknowledgement."""

    model_config = ConfigDict(frozen=True)

    object_id: str = Field(..., min_length=1)


class DecisionTraceStepDTO(BaseModel):
    """Wire projection of DecisionTraceStep."""

    model_config = ConfigDict(frozen=True)

    object_id: str
    step_label: str
    priority_before: str | None = None
    priority_after: str
    detail: str


class DecisionTraceResponse(BaseModel):
    """Wire contract for the trace debug endpoint."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    trace_version: str
    steps: list[DecisionTraceStepDTO] = Field(default_factory=list)
    plan_etag: str


class StoryStatusResponse(BaseModel):
    """Wire contract for GET .../workspace/story/status (additive)."""

    model_config = ConfigDict(frozen=True)

    story_status: str
    context_hash: str
    stale: bool = False
    plan_etag: str | None = None
