"""One-way domain → DTO mappers for Doctor Workspace (no DTO→domain)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum

from app.modules.workspace.domain.models import (
    ClinicalStory,
    CognitiveBudget,
    DecisionQueueItem,
    DecisionTrace,
    DecisionTraceStep,
    LayoutDirective,
    TrustDescriptor,
    WorkspacePlan,
    WorkspacePlanMetadata,
)
from app.modules.workspace.interface.dto import (
    CONTRACT_VERSION,
    ClinicalStoryDTO,
    CognitiveBudgetDTO,
    DecisionQueueItemDTO,
    DecisionTraceResponse,
    DecisionTraceStepDTO,
    LayoutDirectiveDTO,
    PlanMetadataDTO,
    TrustDescriptorDTO,
    WorkspacePlanResponse,
)


def enum_to_wire(value: Enum | str) -> str:
    """Normalize domain enum (or string) to wire string form."""
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def confidence_to_wire(value: float | str) -> float | None:
    """Domain confidence → wire: ``\"unknown\"`` becomes ``null``."""
    if value == "unknown":
        return None
    return float(value)


def format_utc_z(dt: datetime) -> str:
    """Serialize datetime as ISO-8601 UTC with ``Z`` suffix."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_plan_etag(
    *,
    context_hash: str,
    workspace_plan_version: str,
    contract_version: str,
    lens: str,
    role: str,
    acknowledgement_state_version: str,
) -> str:
    """
    SHA-256 of pipe-separated canonical etag payload.

    Components (order fixed):
    context_hash | workspace_plan_version | contract_version | lens | role |
    acknowledgement_state_version
    """
    canonical_payload = "|".join(
        [
            context_hash,
            workspace_plan_version,
            contract_version,
            lens,
            role,
            acknowledgement_state_version,
        ]
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


def _trust_to_dto(trust: TrustDescriptor) -> TrustDescriptorDTO:
    return TrustDescriptorDTO(
        primary_provenance=enum_to_wire(trust.primary_provenance),
        all_provenance=[enum_to_wire(p) for p in trust.all_provenance],
        confidence=confidence_to_wire(trust.confidence),
        verification=enum_to_wire(trust.verification),
        evidence_refs=list(trust.evidence_refs),
    )


def _directive_to_dto(directive: LayoutDirective) -> LayoutDirectiveDTO:
    return LayoutDirectiveDTO(
        object_id=enum_to_wire(directive.object_id),
        priority=enum_to_wire(directive.priority),
        slot=enum_to_wire(directive.slot),
        size=enum_to_wire(directive.size),
        pinned=directive.pinned,
        trust=_trust_to_dto(directive.trust),
        flags=list(directive.flags),
        visibility_reason=(
            enum_to_wire(directive.visibility_reason)
            if directive.visibility_reason is not None
            else None
        ),
    )


def _queue_item_to_dto(item: DecisionQueueItem) -> DecisionQueueItemDTO:
    return DecisionQueueItemDTO(
        rank=item.rank,
        object_id=enum_to_wire(item.object_id),
        reason_code=enum_to_wire(item.reason_code),
        explanation=item.explanation,
        acknowledge_required=item.acknowledge_required,
    )


def _budget_to_dto(budget: CognitiveBudget) -> CognitiveBudgetDTO:
    return CognitiveBudgetDTO(
        primary_count=budget.primary_count,
        expanded_count=budget.expanded_count,
        deferred_count=budget.deferred_count,
    )


def _story_to_dto(story: ClinicalStory) -> ClinicalStoryDTO:
    return ClinicalStoryDTO(
        text=story.text,
        confidence=confidence_to_wire(story.confidence),
        evidence_refs=list(story.evidence_refs),
        stale=story.stale,
    )


def _metadata_to_dto(metadata: WorkspacePlanMetadata) -> PlanMetadataDTO:
    return PlanMetadataDTO(
        context_hash=metadata.context_hash,
        lens=enum_to_wire(metadata.lens),
        role=enum_to_wire(metadata.role),
        computed_at=format_utc_z(metadata.computed_at),
        workspace_plan_version=metadata.workspace_plan_version,
        generated_at=format_utc_z(metadata.generated_at),
        generated_by=metadata.generated_by,
        compute_duration_ms=metadata.compute_duration_ms,
    )


def _trace_step_to_dto(step: DecisionTraceStep) -> DecisionTraceStepDTO:
    return DecisionTraceStepDTO(
        object_id=enum_to_wire(step.object_id),
        step_label=step.step_label,
        priority_before=(
            enum_to_wire(step.priority_before)
            if step.priority_before is not None
            else None
        ),
        priority_after=enum_to_wire(step.priority_after),
        detail=step.detail,
    )


def to_workspace_plan_response(
    plan: WorkspacePlan,
    *,
    acknowledgement_state_version: str = "0",
) -> WorkspacePlanResponse:
    """Map domain WorkspacePlan → WorkspacePlanResponse (drops decision_trace)."""
    meta = plan.metadata
    plan_etag = compute_plan_etag(
        context_hash=meta.context_hash,
        workspace_plan_version=meta.workspace_plan_version,
        contract_version=CONTRACT_VERSION,
        lens=enum_to_wire(meta.lens),
        role=enum_to_wire(meta.role),
        acknowledgement_state_version=acknowledgement_state_version,
    )
    return WorkspacePlanResponse(
        contract_version=CONTRACT_VERSION,
        session_id=plan.session_id,
        workspace_state=enum_to_wire(plan.workspace_state),
        layout_directives=[_directive_to_dto(d) for d in plan.layout_directives],
        decision_queue=[_queue_item_to_dto(i) for i in plan.decision_queue.items],
        story=_story_to_dto(plan.story) if plan.story is not None else None,
        pin_zone=[enum_to_wire(oid) for oid in plan.pin_zone],
        cognitive_budget=_budget_to_dto(plan.cognitive_budget),
        metadata=_metadata_to_dto(meta),
        plan_etag=plan_etag,
    )


def to_decision_trace_response(
    plan: WorkspacePlan,
    plan_etag: str,
) -> DecisionTraceResponse:
    """Map plan.decision_trace → DecisionTraceResponse (empty steps if absent)."""
    trace: DecisionTrace | None = plan.decision_trace
    if trace is None:
        return DecisionTraceResponse(
            session_id=plan.session_id,
            trace_version="1.0.0",
            steps=[],
            plan_etag=plan_etag,
        )
    return DecisionTraceResponse(
        session_id=plan.session_id,
        trace_version=trace.trace_version,
        steps=[_trace_step_to_dto(s) for s in trace.steps],
        plan_etag=plan_etag,
    )
