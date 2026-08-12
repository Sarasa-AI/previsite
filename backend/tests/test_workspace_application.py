"""Workspace application-layer tests — determinism and invariant preservation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.workspace.application.generate_workspace import GenerateWorkspaceUseCase
from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    ReviewAcknowledgements,
    SessionState,
    ValidatedConflict,
)
from app.modules.workspace.application.workspace_orchestrator import WorkspaceOrchestrator
from app.modules.workspace.domain.enums import (
    AttentionSlot,
    ClinicalObjectId,
    PriorityLevel,
    RoleProfile,
    SizeHint,
    SpecialtyLens,
    VisibilityReason,
    WorkspaceState,
)
from app.modules.workspace.domain.models import WorkspacePlan
from app.schemas.clinical_context import (
    ClinicalContext,
    LabEvidence,
    MedicationEvidence,
)
from app.schemas.intake import CurrentMedication, LabResult, MedicalOverview
from app.schemas.medical import MedicalSummary
from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    TemporalKind,
    TemporalPrecision,
    TemporalStatus,
)
from app.modules.timeline.domain.models import (
    ClinicalTimeline,
    TemporalExpression,
    TimelineEvent,
)

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)


def _timeline(*labels: str) -> ClinicalTimeline:
    events = []
    for i, label in enumerate(labels):
        events.append(
            TimelineEvent(
                event_id=f"e{i}",
                event_type=EventType.SYMPTOM_ONGOING,
                clinical_category=ClinicalCategory.SYMPTOM,
                label=label,
                temporal=TemporalExpression(
                    kind=TemporalKind.RELATIVE_DURATION,
                    raw_text="2 days",
                    relative_value=2,
                    relative_unit="days",
                    precision=TemporalPrecision.DAY,
                    uncertainty=False,
                ),
                status=TemporalStatus.ONGOING,
                source=EventSource.HPI,
            )
        )
    return ClinicalTimeline(
        session_id=1,
        patient_id=1,
        anchor_at=FIXED_NOW,
        events=tuple(events),
    )


def _context(**overrides) -> ClinicalContext:
    base = {
        "session_id": 1,
        "patient_id": 7,
        "summary": MedicalSummary(
            chief_complaint="Headache for two days",
            extracted_at=FIXED_NOW,
        ),
        "overview": MedicalOverview(
            allergies="Penicillin",
            current_medications=[
                CurrentMedication(id="m1", name="Metformin", amount="500mg", frequency="BID")
            ],
            lab_results=[
                LabResult(id="l1", name="BMP", extracted_data="Potassium 6.5 mEq/L critical")
            ],
        ),
        "lab_evidence": (
            LabEvidence(lab_id="l1", name="BMP", extracted_data="Potassium 6.5 critical"),
        ),
        "medication_evidence": (
            MedicationEvidence(medication_id="m1", name="Metformin"),
        ),
        "timeline": _timeline("Headache onset", "Nausea", "Photophobia"),
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _plan(
    ctx: ClinicalContext | None = None,
    *,
    session: SessionState | None = None,
    inputs: OrchestratorInputs | None = None,
    lens: SpecialtyLens = SpecialtyLens.GENERAL_MEDICINE,
    role: RoleProfile = RoleProfile.DOCTOR,
    review: ReviewAcknowledgements | None = None,
    now: datetime = FIXED_NOW,
) -> WorkspacePlan:
    return WorkspaceOrchestrator().compute(
        ctx or _context(),
        session_state=session or SessionState(soap_status="ready", soap_exists=True, verification_status="verified"),
        inputs=inputs
        or OrchestratorInputs(
            red_flags=("Chest pain",),
            patient_questions=("Is this serious?",),
            validated_conflicts=(
                ValidatedConflict(concept="diabetes", confidence="high", involves_medication=True),
            ),
            document_count=1,
        ),
        lens=lens,
        role=role,
        review_state=review,
        now=now,
        include_trace=True,
    )


def _stable_fields(plan: WorkspacePlan) -> dict:
    """Compare plans ignoring wall-clock / duration metadata."""
    data = plan.model_dump(mode="json")
    data["metadata"].pop("generated_at", None)
    data["metadata"].pop("computed_at", None)
    data["metadata"].pop("compute_duration_ms", None)
    return data


# ── Determinism ──────────────────────────────────────────────────────────────


def test_identical_inputs_produce_identical_plan_core() -> None:
    a = _plan()
    b = _plan()
    assert _stable_fields(a) == _stable_fields(b)


def test_use_case_matches_orchestrator() -> None:
    ctx = _context()
    session = SessionState(soap_status="ready", soap_exists=True, verification_status="verified")
    inputs = OrchestratorInputs(red_flags=("syncope",), document_count=0)
    via_orch = WorkspaceOrchestrator().compute(
        ctx, session_state=session, inputs=inputs, now=FIXED_NOW
    )
    via_uc = GenerateWorkspaceUseCase().execute(
        ctx, session_state=session, inputs=inputs, now=FIXED_NOW
    )
    assert _stable_fields(via_orch) == _stable_fields(via_uc)


def test_context_not_mutated() -> None:
    ctx = _context()
    before = ctx.model_dump(mode="json")
    _plan(ctx)
    assert ctx.model_dump(mode="json") == before


# ── Domain invariant preservation ────────────────────────────────────────────


def test_plan_validates_against_domain_model() -> None:
    plan = _plan()
    # Round-trip through domain model
    restored = WorkspacePlan.model_validate(plan.model_dump())
    assert restored.session_id == plan.session_id
    assert len(restored.layout_directives) == len(list(ClinicalObjectId))


def test_every_hidden_has_visibility_reason() -> None:
    plan = _plan()
    for d in plan.layout_directives:
        if d.slot is AttentionSlot.HIDDEN:
            assert d.visibility_reason is not None
        else:
            assert d.visibility_reason is None


def test_pin_zone_objects_are_pinned() -> None:
    plan = _plan()
    by_id = {d.object_id: d for d in plan.layout_directives}
    for oid in plan.pin_zone:
        assert by_id[oid].pinned is True
        assert by_id[oid].slot is AttentionSlot.PIN


def test_queue_explanations_deterministic_and_nonempty() -> None:
    a = _plan()
    b = _plan()
    assert [i.explanation for i in a.decision_queue.items] == [
        i.explanation for i in b.decision_queue.items
    ]
    assert all(i.explanation.strip() for i in a.decision_queue.items)
    ranks = [i.rank for i in a.decision_queue.items]
    assert ranks == list(range(1, len(ranks) + 1))


def test_decision_trace_records_transitions() -> None:
    plan = _plan()
    assert plan.decision_trace is not None
    assert len(plan.decision_trace.steps) > 0
    assert plan.metadata.workspace_plan_version


def test_max_three_visible_p0() -> None:
    plan = _plan()
    p0 = [
        d
        for d in plan.layout_directives
        if d.priority is PriorityLevel.P0 and d.slot is not AttentionSlot.HIDDEN
    ]
    assert len(p0) <= 3


# ── Behavioral scenarios ─────────────────────────────────────────────────────


def test_empty_labs_and_meds_hidden() -> None:
    ctx = _context(
        overview=MedicalOverview(allergies="NKDA"),
        lab_evidence=(),
        medication_evidence=(),
        summary=MedicalSummary(
            chief_complaint="Follow-up",
            allergies=["NKDA"],
            extracted_at=FIXED_NOW,
        ),
        timeline=_timeline("a", "b", "c"),
    )
    plan = _plan(
        ctx,
        inputs=OrchestratorInputs(),
        session=SessionState(soap_status="ready", soap_exists=True, verification_status="verified"),
    )
    by_id = {d.object_id: d for d in plan.layout_directives}
    assert by_id[ClinicalObjectId.LABS].slot is AttentionSlot.HIDDEN
    assert by_id[ClinicalObjectId.LABS].visibility_reason is VisibilityReason.NO_DATA
    assert by_id[ClinicalObjectId.MEDICATIONS].slot is AttentionSlot.HIDDEN


def test_medications_expanded_when_count_gt_10() -> None:
    meds = [
        CurrentMedication(id=f"m{i}", name=f"Drug{i}") for i in range(11)
    ]
    ctx = _context(
        overview=MedicalOverview(allergies="Penicillin", current_medications=meds),
        medication_evidence=tuple(
            MedicationEvidence(medication_id=f"m{i}", name=f"Drug{i}") for i in range(11)
        ),
        lab_evidence=(),
    )
    plan = _plan(
        ctx,
        inputs=OrchestratorInputs(document_count=0),
        session=SessionState(soap_status="ready", soap_exists=True),
    )
    med = next(d for d in plan.layout_directives if d.object_id is ClinicalObjectId.MEDICATIONS)
    assert med.size is SizeHint.EXPANDED


def test_soap_generating_is_badge_deferred_excluded_from_queue() -> None:
    plan = _plan(
        session=SessionState(soap_status="generating", soap_exists=True),
    )
    soap = next(d for d in plan.layout_directives if d.object_id is ClinicalObjectId.SOAP)
    assert soap.size is SizeHint.BADGE
    assert soap.slot is AttentionSlot.DEFERRED
    assert ClinicalObjectId.SOAP not in {i.object_id for i in plan.decision_queue.items}
    assert plan.workspace_state is WorkspaceState.GENERATING


def test_validated_conflicts_drive_conflict_present_state() -> None:
    plan = _plan(
        inputs=OrchestratorInputs(
            validated_conflicts=(
                ValidatedConflict(concept="med conflict", confidence="high"),
            ),
            red_flags=(),
        ),
        review=ReviewAcknowledgements(),
    )
    conflicts = next(
        d for d in plan.layout_directives if d.object_id is ClinicalObjectId.CONFLICTS
    )
    assert conflicts.priority is PriorityLevel.P0
    assert conflicts.slot is AttentionSlot.PIN
    assert plan.workspace_state in {
        WorkspaceState.CONFLICT_PRESENT,
        WorkspaceState.REVIEW_NEEDED,
    }


def test_nurse_role_hides_story() -> None:
    plan = _plan(role=RoleProfile.NURSE)
    story = next(d for d in plan.layout_directives if d.object_id is ClinicalObjectId.STORY)
    assert story.slot is AttentionSlot.HIDDEN
    assert story.visibility_reason is VisibilityReason.SPECIALTY_FILTER
    assert plan.story is None


def test_endocrinology_lens_changes_queue_not_structure() -> None:
    general = _plan(lens=SpecialtyLens.GENERAL_MEDICINE)
    endo = _plan(lens=SpecialtyLens.ENDOCRINOLOGY)
    # Same set of object ids in directives
    assert {d.object_id for d in general.layout_directives} == {
        d.object_id for d in endo.layout_directives
    }
    # Queue order may differ
    g_order = [i.object_id for i in general.decision_queue.items]
    e_order = [i.object_id for i in endo.decision_queue.items]
    # Both valid contiguous queues
    assert len(g_order) == len(set(g_order))
    assert len(e_order) == len(set(e_order))


def test_story_generated_when_evidence_sufficient() -> None:
    plan = _plan()
    assert plan.story is not None
    assert plan.story.evidence_refs
    assert len(plan.story.text.split()) <= 60


def test_missing_chief_complaint_promotes_missing_data() -> None:
    ctx = _context(summary=MedicalSummary(chief_complaint=None, extracted_at=FIXED_NOW))
    plan = _plan(ctx, inputs=OrchestratorInputs(allergies_status_unknown=True))
    missing = next(
        d for d in plan.layout_directives if d.object_id is ClinicalObjectId.MISSING_DATA
    )
    assert missing.priority is PriorityLevel.P0
    assert missing.slot is AttentionSlot.PIN
    assert ClinicalObjectId.MISSING_DATA in plan.pin_zone


def test_offline_state() -> None:
    plan = _plan(session=SessionState(offline=True, soap_status="ready", soap_exists=True))
    assert plan.workspace_state is WorkspaceState.OFFLINE


def test_safety_before_soap_in_queue() -> None:
    plan = _plan(
        session=SessionState(
            soap_status="ready",
            soap_exists=True,
            verification_status="unverified",
        ),
    )
    ids = [i.object_id for i in plan.decision_queue.items]
    safety = {
        ClinicalObjectId.CONFLICTS,
        ClinicalObjectId.ALLERGIES,
        ClinicalObjectId.RED_FLAGS,
        ClinicalObjectId.CRITICAL_LABS,
        ClinicalObjectId.MISSING_DATA,
    }
    if ClinicalObjectId.SOAP in ids:
        soap_idx = ids.index(ClinicalObjectId.SOAP)
        for sid in safety:
            if sid in ids:
                assert ids.index(sid) < soap_idx


def test_dismiss_hides_with_physician_dismissed() -> None:
    plan = _plan(
        review=ReviewAcknowledgements(
            dismissed_objects=frozenset({ClinicalObjectId.LABS}),
        ),
    )
    labs = next(d for d in plan.layout_directives if d.object_id is ClinicalObjectId.LABS)
    assert labs.slot is AttentionSlot.HIDDEN
    assert labs.visibility_reason is VisibilityReason.PHYSICIAN_DISMISSED
    assert ClinicalObjectId.LABS not in {
        i.object_id for i in plan.decision_queue.items
    }


def test_dismiss_does_not_clear_p0_ack_gate() -> None:
    """Dismiss is visibility-only; P0 gate remains until ack/resolve (§6.4)."""
    plan = _plan(
        inputs=OrchestratorInputs(
            validated_conflicts=(ValidatedConflict(concept="med", confidence="high"),),
        ),
        review=ReviewAcknowledgements(
            dismissed_objects=frozenset({ClinicalObjectId.CONFLICTS}),
        ),
        session=SessionState(soap_status="ready", soap_exists=True),
    )
    conflicts = next(
        d for d in plan.layout_directives if d.object_id is ClinicalObjectId.CONFLICTS
    )
    assert conflicts.slot is AttentionSlot.HIDDEN
    assert conflicts.visibility_reason is VisibilityReason.PHYSICIAN_DISMISSED
    assert plan.workspace_state in {
        WorkspaceState.CONFLICT_PRESENT,
        WorkspaceState.REVIEW_NEEDED,
    }


def test_resolve_omits_from_active_queue() -> None:
    plan = _plan(
        review=ReviewAcknowledgements(
            resolved_objects=frozenset({ClinicalObjectId.MEDICATIONS}),
        ),
    )
    assert ClinicalObjectId.MEDICATIONS not in {
        i.object_id for i in plan.decision_queue.items
    }
    # Resolve does not force-hide via physician_dismissed
    meds = next(
        d for d in plan.layout_directives if d.object_id is ClinicalObjectId.MEDICATIONS
    )
    assert meds.visibility_reason is not VisibilityReason.PHYSICIAN_DISMISSED


def test_resolve_clears_p0_ack_gate() -> None:
    plan = _plan(
        inputs=OrchestratorInputs(
            validated_conflicts=(ValidatedConflict(concept="med", confidence="high"),),
        ),
        review=ReviewAcknowledgements(
            resolved_objects=frozenset({ClinicalObjectId.CONFLICTS}),
        ),
        session=SessionState(
            soap_status="ready",
            soap_exists=True,
            verification_status="verified",
            soap_accepted=True,
        ),
    )
    assert plan.workspace_state is not WorkspaceState.CONFLICT_PRESENT
    queue_conflicts = [
        i for i in plan.decision_queue.items if i.object_id is ClinicalObjectId.CONFLICTS
    ]
    assert queue_conflicts == []


def test_never_hide_objects_ignore_dismiss() -> None:
    plan = _plan(
        review=ReviewAcknowledgements(
            dismissed_objects=frozenset(
                {
                    ClinicalObjectId.CHIEF_COMPLAINT,
                    ClinicalObjectId.ALLERGIES,
                    ClinicalObjectId.SNAPSHOT,
                }
            ),
        ),
    )
    for oid in (
        ClinicalObjectId.CHIEF_COMPLAINT,
        ClinicalObjectId.ALLERGIES,
        ClinicalObjectId.SNAPSHOT,
    ):
        d = next(x for x in plan.layout_directives if x.object_id is oid)
        assert d.slot is not AttentionSlot.HIDDEN or d.visibility_reason is not (
            VisibilityReason.PHYSICIAN_DISMISSED
        )
        if d.visibility_reason is VisibilityReason.PHYSICIAN_DISMISSED:
            pytest.fail(f"{oid} must not be physician_dismissed")
