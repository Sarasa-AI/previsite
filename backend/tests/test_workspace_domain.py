"""Workspace domain invariant tests (no orchestrator / API / DB)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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
from app.modules.workspace.domain.models import (
    ClinicalStory,
    CognitiveBudget,
    DecisionQueue,
    DecisionQueueItem,
    DecisionTrace,
    DecisionTraceStep,
    LayoutDirective,
    TrustDescriptor,
    WorkspacePlan,
    WorkspacePlanMetadata,
)

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)


def _trust(**overrides) -> TrustDescriptor:
    base = {
        "primary_provenance": TrustProvenance.SYSTEM_DERIVED,
        "all_provenance": (TrustProvenance.SYSTEM_DERIVED,),
        "confidence": 1.0,
        "verification": TrustVerification.NA,
    }
    base.update(overrides)
    return TrustDescriptor(**base)


def _directive(**overrides) -> LayoutDirective:
    base = {
        "object_id": ClinicalObjectId.CHIEF_COMPLAINT,
        "priority": PriorityLevel.P1,
        "slot": AttentionSlot.PIN,
        "size": SizeHint.STANDARD,
        "pinned": True,
        "trust": _trust(),
    }
    base.update(overrides)
    return LayoutDirective(**base)


def _metadata(**overrides) -> WorkspacePlanMetadata:
    base = {
        "context_hash": "abc123",
        "lens": SpecialtyLens.GENERAL_MEDICINE,
        "role": RoleProfile.DOCTOR,
        "computed_at": NOW,
        "generated_at": NOW,
        "compute_duration_ms": 12,
    }
    base.update(overrides)
    return WorkspacePlanMetadata(**base)


def _budget(**overrides) -> CognitiveBudget:
    base = {"primary_count": 1, "expanded_count": 0, "deferred_count": 0}
    base.update(overrides)
    return CognitiveBudget(**base)


# ── Immutability ─────────────────────────────────────────────────────────────


def test_models_are_frozen() -> None:
    trust = _trust()
    with pytest.raises(ValidationError):
        trust.confidence = 0.5  # type: ignore[misc]

    directive = _directive()
    with pytest.raises(ValidationError):
        directive.pinned = False  # type: ignore[misc]

    plan = WorkspacePlan(
        session_id=1,
        workspace_state=WorkspaceState.REVIEW_NEEDED,
        layout_directives=(_directive(),),
        pin_zone=(ClinicalObjectId.CHIEF_COMPLAINT,),
        cognitive_budget=_budget(),
        metadata=_metadata(),
    )
    with pytest.raises(ValidationError):
        plan.session_id = 99  # type: ignore[misc]


# ── VisibilityReason invariant ───────────────────────────────────────────────


def test_hidden_requires_visibility_reason() -> None:
    with pytest.raises(ValidationError, match="visibility_reason is required"):
        _directive(
            object_id=ClinicalObjectId.LABS,
            priority=PriorityLevel.P3,
            slot=AttentionSlot.HIDDEN,
            size=SizeHint.COMPRESSED,
            pinned=False,
            visibility_reason=None,
        )


def test_hidden_with_visibility_reason_ok() -> None:
    d = _directive(
        object_id=ClinicalObjectId.LABS,
        priority=PriorityLevel.P3,
        slot=AttentionSlot.HIDDEN,
        size=SizeHint.COMPRESSED,
        pinned=False,
        visibility_reason=VisibilityReason.NO_DATA,
    )
    assert d.visibility_reason is VisibilityReason.NO_DATA


def test_visible_rejects_visibility_reason() -> None:
    with pytest.raises(ValidationError, match="must be null when slot is not hidden"):
        _directive(visibility_reason=VisibilityReason.NO_DATA)


# ── Pin invariants ───────────────────────────────────────────────────────────


def test_pin_slot_requires_pinned_true() -> None:
    with pytest.raises(ValidationError, match="slot pin requires pinned=True"):
        _directive(pinned=False)


def test_hidden_cannot_be_pinned() -> None:
    with pytest.raises(ValidationError, match="cannot be pinned"):
        _directive(
            object_id=ClinicalObjectId.STORY,
            slot=AttentionSlot.HIDDEN,
            pinned=True,
            visibility_reason=VisibilityReason.NO_DATA,
        )


# ── TrustDescriptor ──────────────────────────────────────────────────────────


def test_trust_confidence_bounds() -> None:
    with pytest.raises(ValidationError, match="confidence"):
        _trust(confidence=1.5)
    with pytest.raises(ValidationError, match="confidence"):
        _trust(confidence=-0.1)
    assert _trust(confidence="unknown").confidence == "unknown"


def test_primary_provenance_must_be_in_all() -> None:
    with pytest.raises(ValidationError, match="primary_provenance"):
        _trust(
            primary_provenance=TrustProvenance.AI_GENERATED,
            all_provenance=(TrustProvenance.PATIENT_REPORTED,),
        )


# ── DecisionQueue ────────────────────────────────────────────────────────────


def test_queue_ranks_must_be_contiguous_from_one() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        DecisionQueue(
            items=(
                DecisionQueueItem(
                    rank=2,
                    object_id=ClinicalObjectId.CHIEF_COMPLAINT,
                    reason_code=ReasonCode.ORIENT,
                    explanation="Visit orientation",
                ),
            )
        )


def test_queue_object_ids_must_be_unique() -> None:
    with pytest.raises(ValidationError, match="unique"):
        DecisionQueue(
            items=(
                DecisionQueueItem(
                    rank=1,
                    object_id=ClinicalObjectId.CONFLICTS,
                    reason_code=ReasonCode.SAFETY,
                    explanation="Safety first",
                ),
                DecisionQueueItem(
                    rank=2,
                    object_id=ClinicalObjectId.CONFLICTS,
                    reason_code=ReasonCode.SAFETY,
                    explanation="Duplicate",
                ),
            )
        )


def test_queue_explanation_required() -> None:
    with pytest.raises(ValidationError):
        DecisionQueueItem(
            rank=1,
            object_id=ClinicalObjectId.CHIEF_COMPLAINT,
            reason_code=ReasonCode.ORIENT,
            explanation="",
        )


# ── ClinicalStory ────────────────────────────────────────────────────────────


def test_story_requires_evidence_refs() -> None:
    with pytest.raises(ValidationError, match="evidence_ref"):
        ClinicalStory(text="Patient presents with headache.", evidence_refs=())


def test_story_word_limit() -> None:
    words = " ".join(["word"] * 61)
    with pytest.raises(ValidationError, match="60 words"):
        ClinicalStory(text=words, evidence_refs=("summary.chief_complaint",))


def test_story_sentence_limit() -> None:
    text = "One. Two. Three. Four. Five."
    with pytest.raises(ValidationError, match="4 sentences"):
        ClinicalStory(text=text, evidence_refs=("summary.chief_complaint",))


def test_story_valid_minimal() -> None:
    story = ClinicalStory(
        text="Patient presents with headache for three days.",
        confidence=0.8,
        evidence_refs=("summary.chief_complaint",),
    )
    assert story.stale is False


# ── WorkspacePlan composition ────────────────────────────────────────────────


def test_plan_pin_zone_must_match_pin_directives() -> None:
    with pytest.raises(ValidationError, match="pin_zone"):
        WorkspacePlan(
            session_id=1,
            workspace_state=WorkspaceState.LOADING,
            layout_directives=(_directive(),),
            pin_zone=(ClinicalObjectId.ALLERGIES,),
            cognitive_budget=_budget(),
            metadata=_metadata(),
        )


def test_plan_rejects_hidden_queue_items() -> None:
    hidden_labs = _directive(
        object_id=ClinicalObjectId.LABS,
        priority=PriorityLevel.P3,
        slot=AttentionSlot.HIDDEN,
        size=SizeHint.COMPRESSED,
        pinned=False,
        visibility_reason=VisibilityReason.NO_DATA,
    )
    queue = DecisionQueue(
        items=(
            DecisionQueueItem(
                rank=1,
                object_id=ClinicalObjectId.LABS,
                reason_code=ReasonCode.EVIDENCE,
                explanation="Should not be queued",
            ),
        )
    )
    with pytest.raises(ValidationError, match="cannot include hidden"):
        WorkspacePlan(
            session_id=1,
            workspace_state=WorkspaceState.REVIEW_NEEDED,
            layout_directives=(_directive(), hidden_labs),
            decision_queue=queue,
            pin_zone=(ClinicalObjectId.CHIEF_COMPLAINT,),
            cognitive_budget=_budget(),
            metadata=_metadata(),
        )


def test_plan_max_three_visible_p0() -> None:
    def p0(oid: ClinicalObjectId) -> LayoutDirective:
        return _directive(
            object_id=oid,
            priority=PriorityLevel.P0,
            slot=AttentionSlot.PIN,
            size=SizeHint.EXPANDED,
            pinned=True,
        )

    directives = (
        p0(ClinicalObjectId.CONFLICTS),
        p0(ClinicalObjectId.ALLERGIES),
        p0(ClinicalObjectId.RED_FLAGS),
        p0(ClinicalObjectId.CRITICAL_LABS),
    )
    with pytest.raises(ValidationError, match="at most 3 visible P0"):
        WorkspacePlan(
            session_id=1,
            workspace_state=WorkspaceState.CONFLICT_PRESENT,
            layout_directives=directives,
            pin_zone=(
                ClinicalObjectId.CONFLICTS,
                ClinicalObjectId.ALLERGIES,
                ClinicalObjectId.RED_FLAGS,
                ClinicalObjectId.CRITICAL_LABS,
            ),
            cognitive_budget=_budget(primary_count=0, expanded_count=4),
            metadata=_metadata(),
        )


def test_plan_valid_minimal() -> None:
    plan = WorkspacePlan(
        session_id=42,
        workspace_state=WorkspaceState.REVIEW_NEEDED,
        layout_directives=(
            _directive(),
            _directive(
                object_id=ClinicalObjectId.LABS,
                priority=PriorityLevel.P3,
                slot=AttentionSlot.HIDDEN,
                size=SizeHint.COMPRESSED,
                pinned=False,
                visibility_reason=VisibilityReason.NO_DATA,
            ),
        ),
        decision_queue=DecisionQueue(
            items=(
                DecisionQueueItem(
                    rank=1,
                    object_id=ClinicalObjectId.CHIEF_COMPLAINT,
                    reason_code=ReasonCode.ORIENT,
                    explanation="Chief complaint orients the visit",
                ),
            )
        ),
        story=ClinicalStory(
            text="Patient presents for headache review.",
            confidence=0.7,
            evidence_refs=("summary.chief_complaint",),
        ),
        pin_zone=(ClinicalObjectId.CHIEF_COMPLAINT,),
        cognitive_budget=_budget(primary_count=1),
        decision_trace=DecisionTrace(
            steps=(
                DecisionTraceStep(
                    object_id=ClinicalObjectId.CHIEF_COMPLAINT,
                    step_label="base_priority",
                    priority_before=None,
                    priority_after=PriorityLevel.P1,
                    detail="Default P1 when chief complaint present",
                ),
            )
        ),
        metadata=_metadata(),
    )
    assert plan.session_id == 42
    assert plan.metadata.workspace_plan_version == "1.0.0"
    assert plan.decision_trace is not None
    assert len(plan.decision_trace.steps) == 1
    # Hidden directive retained for explainability
    hidden = [d for d in plan.layout_directives if d.slot is AttentionSlot.HIDDEN]
    assert len(hidden) == 1
    assert hidden[0].visibility_reason is VisibilityReason.NO_DATA


def test_metadata_rejects_negative_duration() -> None:
    with pytest.raises(ValidationError):
        _metadata(compute_duration_ms=-1)


def test_cognitive_budget_non_negative() -> None:
    with pytest.raises(ValidationError):
        CognitiveBudget(primary_count=-1, expanded_count=0, deferred_count=0)


def test_duplicate_layout_object_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="unique"):
        WorkspacePlan(
            session_id=1,
            workspace_state=WorkspaceState.LOADING,
            layout_directives=(_directive(), _directive()),
            pin_zone=(ClinicalObjectId.CHIEF_COMPLAINT,),
            cognitive_budget=_budget(),
            metadata=_metadata(),
        )
