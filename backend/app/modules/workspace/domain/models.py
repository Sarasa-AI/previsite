"""Immutable Doctor Workspace domain models."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
    ReasonCode,
    RoleProfile,
    SizeHint,
    SpecialtyLens,
    TrustProvenance,
    TrustVerification,
    VisibilityReason,
    WorkspaceState,
)

ConfidenceValue = float | Literal["unknown"]

# Story Engine length limits (orchestration §7.6) — domain invariants.
STORY_MAX_WORDS = 60
STORY_MAX_CHARS = 400
STORY_MAX_SENTENCES = 4

# Default algorithm / trace schema versions (observability metadata).
WORKSPACE_PLAN_VERSION = "1.0.0"
TRACE_VERSION = "1.0.0"
GENERATED_BY = "workspace-orchestrator@1.0.0"


class TrustDescriptor(BaseModel):
    """Clinical provenance behavior attached to every LayoutDirective."""

    model_config = ConfigDict(frozen=True)

    primary_provenance: TrustProvenance
    all_provenance: tuple[TrustProvenance, ...] = ()
    confidence: ConfidenceValue = "unknown"
    verification: TrustVerification = TrustVerification.NA
    evidence_refs: tuple[str, ...] = ()

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: ConfidenceValue) -> ConfidenceValue:
        if value == "unknown":
            return value
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0] or 'unknown'")
        return float(value)

    @model_validator(mode="after")
    def _primary_in_all(self) -> TrustDescriptor:
        if self.all_provenance and self.primary_provenance not in self.all_provenance:
            raise ValueError("primary_provenance must appear in all_provenance when set")
        return self


class LayoutDirective(BaseModel):
    """Per-object layout directive emitted in WorkspacePlan."""

    model_config = ConfigDict(frozen=True)

    object_id: ClinicalObjectId
    priority: PriorityLevel
    slot: AttentionSlot
    size: SizeHint
    pinned: bool = False
    trust: TrustDescriptor
    flags: tuple[str, ...] = ()
    visibility_reason: VisibilityReason | None = None

    @model_validator(mode="after")
    def _visibility_reason_invariant(self) -> LayoutDirective:
        if self.slot is AttentionSlot.HIDDEN:
            if self.visibility_reason is None:
                raise ValueError(
                    "visibility_reason is required when slot is hidden"
                )
        elif self.visibility_reason is not None:
            raise ValueError(
                "visibility_reason must be null when slot is not hidden"
            )
        return self

    @model_validator(mode="after")
    def _pin_invariant(self) -> LayoutDirective:
        if self.slot is AttentionSlot.PIN and not self.pinned:
            raise ValueError("slot pin requires pinned=True")
        if self.pinned and self.slot is AttentionSlot.HIDDEN:
            raise ValueError("hidden directives cannot be pinned")
        return self


class DecisionQueueItem(BaseModel):
    """One recommended review step in the Decision Queue."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(..., ge=1)
    object_id: ClinicalObjectId
    reason_code: ReasonCode
    explanation: str = Field(..., min_length=1)
    acknowledge_required: bool = False


class DecisionQueue(BaseModel):
    """Ordered, deterministic recommended review sequence."""

    model_config = ConfigDict(frozen=True)

    items: tuple[DecisionQueueItem, ...] = ()

    @model_validator(mode="after")
    def _contiguous_ranks(self) -> DecisionQueue:
        if not self.items:
            return self
        ranks = [item.rank for item in self.items]
        expected = list(range(1, len(self.items) + 1))
        if ranks != expected:
            raise ValueError(
                f"decision queue ranks must be contiguous from 1; got {ranks}"
            )
        object_ids = [item.object_id for item in self.items]
        if len(object_ids) != len(set(object_ids)):
            raise ValueError("decision queue object_id values must be unique")
        return self


class DecisionTraceStep(BaseModel):
    """Single priority transition recorded during orchestration."""

    model_config = ConfigDict(frozen=True)

    object_id: ClinicalObjectId
    step_label: str = Field(..., min_length=1)
    priority_before: PriorityLevel | None = None
    priority_after: PriorityLevel
    detail: str = Field(..., min_length=1)


class DecisionTrace(BaseModel):
    """Optional explainability artifact for priority promotions/demotions."""

    model_config = ConfigDict(frozen=True)

    trace_version: str = TRACE_VERSION
    steps: tuple[DecisionTraceStep, ...] = ()


class ClinicalStory(BaseModel):
    """Evidence-bound visit narrative (no diagnosis or recommendations)."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(..., min_length=1, max_length=STORY_MAX_CHARS)
    confidence: ConfidenceValue = "unknown"
    evidence_refs: tuple[str, ...] = ()
    stale: bool = False

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: ConfidenceValue) -> ConfidenceValue:
        if value == "unknown":
            return value
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0] or 'unknown'")
        return float(value)

    @model_validator(mode="after")
    def _length_and_evidence(self) -> ClinicalStory:
        words = self.text.split()
        if len(words) > STORY_MAX_WORDS:
            raise ValueError(
                f"story text exceeds {STORY_MAX_WORDS} words (got {len(words)})"
            )
        # Sentence count: non-empty segments split on . ! ?
        sentences = [
            s.strip() for s in re.split(r"[.!?]+", self.text) if s.strip()
        ]
        if len(sentences) > STORY_MAX_SENTENCES:
            raise ValueError(
                f"story text exceeds {STORY_MAX_SENTENCES} sentences "
                f"(got {len(sentences)})"
            )
        if not self.evidence_refs:
            raise ValueError("story must cite at least one evidence_ref")
        return self


class CognitiveBudget(BaseModel):
    """Attention budget counters for the computed plan."""

    model_config = ConfigDict(frozen=True)

    primary_count: int = Field(..., ge=0)
    expanded_count: int = Field(..., ge=0)
    deferred_count: int = Field(..., ge=0)


class WorkspacePlanMetadata(BaseModel):
    """Immutable orchestration metadata (observability / versioning)."""

    model_config = ConfigDict(frozen=True)

    context_hash: str = Field(..., min_length=1)
    lens: SpecialtyLens
    role: RoleProfile
    computed_at: datetime
    workspace_plan_version: str = WORKSPACE_PLAN_VERSION
    generated_at: datetime
    generated_by: str = GENERATED_BY
    compute_duration_ms: int = Field(..., ge=0)


class WorkspacePlan(BaseModel):
    """
    Derived orchestration artifact — physician attention, priority, and layout.

    See docs/architecture/doctor-workspace-orchestration.md.
    Does not modify ClinicalContext.
    """

    model_config = ConfigDict(frozen=True)

    session_id: int
    workspace_state: WorkspaceState
    layout_directives: tuple[LayoutDirective, ...] = ()
    decision_queue: DecisionQueue = Field(default_factory=DecisionQueue)
    story: ClinicalStory | None = None
    pin_zone: tuple[ClinicalObjectId, ...] = ()
    cognitive_budget: CognitiveBudget
    decision_trace: DecisionTrace | None = None
    metadata: WorkspacePlanMetadata

    @model_validator(mode="after")
    def _plan_invariants(self) -> WorkspacePlan:
        directive_ids = [d.object_id for d in self.layout_directives]
        if len(directive_ids) != len(set(directive_ids)):
            raise ValueError("layout_directives object_id values must be unique")

        for object_id in self.pin_zone:
            matches = [
                d for d in self.layout_directives if d.object_id is object_id
            ]
            if not matches:
                raise ValueError(
                    f"pin_zone object {object_id.value} missing from layout_directives"
                )
            directive = matches[0]
            if not directive.pinned or directive.slot is not AttentionSlot.PIN:
                raise ValueError(
                    f"pin_zone object {object_id.value} must have slot=pin and pinned=True"
                )

        for item in self.decision_queue.items:
            matches = [
                d
                for d in self.layout_directives
                if d.object_id is item.object_id
            ]
            if not matches:
                raise ValueError(
                    f"decision queue object {item.object_id.value} "
                    "missing from layout_directives"
                )
            if matches[0].slot is AttentionSlot.HIDDEN:
                raise ValueError(
                    f"decision queue cannot include hidden object "
                    f"{item.object_id.value}"
                )

        p0_count = sum(
            1
            for d in self.layout_directives
            if d.priority is PriorityLevel.P0
            and d.slot is not AttentionSlot.HIDDEN
        )
        if p0_count > 3:
            raise ValueError(
                f"at most 3 visible P0 objects allowed (got {p0_count})"
            )

        return self
