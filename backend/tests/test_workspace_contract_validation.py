"""
Architecture Gate validation — ClinicalContext → WorkspacePlan → DTO.

Field mapping completeness + semantic invariants. Additive tests only;
does not modify production modules.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from app.modules.workspace.application.context_hash import compute_context_hash
from app.modules.workspace.application.inputs import (
    OrchestratorInputs,
    SessionState,
    ValidatedConflict,
)
from app.modules.workspace.application.workspace_orchestrator import WorkspaceOrchestrator
from app.modules.workspace.domain.enums import AttentionSlot, ClinicalObjectId
from app.modules.workspace.domain.models import WorkspacePlan
from app.modules.workspace.interface.dto import CONTRACT_VERSION, WorkspacePlanResponse
from app.modules.workspace.interface.mappers import to_workspace_plan_response
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
from app.schemas.clinical_context import (
    ClinicalContext,
    LabEvidence,
    MedicationEvidence,
)
from app.schemas.intake import CurrentMedication, LabResult, MedicalOverview
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)

ALL_OBJECT_IDS = {oid.value for oid in ClinicalObjectId}

RESPONSE_TOP_LEVEL_KEYS = {
    "contract_version",
    "session_id",
    "workspace_state",
    "layout_directives",
    "decision_queue",
    "story",
    "pin_zone",
    "cognitive_budget",
    "metadata",
    "plan_etag",
}

DIRECTIVE_KEYS = {
    "object_id",
    "priority",
    "slot",
    "size",
    "pinned",
    "trust",
    "flags",
    "visibility_reason",
}

TRUST_KEYS = {
    "primary_provenance",
    "all_provenance",
    "confidence",
    "verification",
    "evidence_refs",
}


def _timeline(*labels: str, count: int | None = None) -> ClinicalTimeline:
    if count is not None:
        labels = tuple(f"Event {i}" for i in range(count))
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
            chief_complaint="Exertional chest tightness for 3 days",
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
        "timeline": _timeline("Chest tightness onset", "Dyspnea", "Diaphoresis"),
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _plan(
    ctx: ClinicalContext | None = None,
    *,
    session: SessionState | None = None,
    inputs: OrchestratorInputs | None = None,
) -> WorkspacePlan:
    return WorkspaceOrchestrator().compute(
        ctx or _context(),
        session_state=session
        or SessionState(soap_status="ready", soap_exists=True, verification_status="verified"),
        inputs=inputs
        or OrchestratorInputs(
            red_flags=("Chest pain", "Syncope"),
            patient_questions=("Is this serious?",),
            validated_conflicts=(
                ValidatedConflict(concept="diabetes", confidence="high", involves_medication=True),
            ),
            document_count=2,
        ),
        now=FIXED_NOW,
        include_trace=True,
    )


def _dto(plan: WorkspacePlan | None = None) -> WorkspacePlanResponse:
    return to_workspace_plan_response(plan or _plan())


# ── Field mapping completeness ───────────────────────────────────────────────


def test_golden_path_response_field_inventory() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    dump = response.model_dump()

    assert set(dump.keys()) == RESPONSE_TOP_LEVEL_KEYS
    assert "decision_trace" not in dump
    assert response.contract_version == CONTRACT_VERSION
    assert response.plan_etag
    assert response.session_id == plan.session_id
    assert response.workspace_state == plan.workspace_state.value

    assert len(response.layout_directives) == len(list(ClinicalObjectId))
    for directive in response.layout_directives:
        assert set(directive.model_dump().keys()) == DIRECTIVE_KEYS
        assert set(directive.trust.model_dump().keys()) == TRUST_KEYS

    assert isinstance(response.decision_queue, list)
    for item in response.decision_queue:
        assert set(item.model_dump().keys()) == {
            "rank",
            "object_id",
            "reason_code",
            "explanation",
            "acknowledge_required",
        }

    meta = response.metadata.model_dump()
    for key in (
        "context_hash",
        "lens",
        "role",
        "computed_at",
        "workspace_plan_version",
        "generated_at",
        "generated_by",
        "compute_duration_ms",
    ):
        assert key in meta

    restored = WorkspacePlanResponse.model_validate(dump)
    assert restored.session_id == response.session_id


def test_confidence_unknown_maps_to_null_never_zero() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    for domain_d, wire_d in zip(plan.layout_directives, response.layout_directives, strict=True):
        if domain_d.trust.confidence == "unknown":
            assert wire_d.trust.confidence is None
            assert wire_d.trust.confidence != 0


def test_partial_null_context_still_validates() -> None:
    ctx = _context(
        overview=None,
        timeline=None,
        lab_evidence=(),
        medication_evidence=(),
        file_analyses=(),
    )
    plan = _plan(ctx, inputs=OrchestratorInputs(document_count=0))
    response = to_workspace_plan_response(plan)
    assert len(response.layout_directives) == len(ALL_OBJECT_IDS)
    for d in response.layout_directives:
        if d.slot == "hidden":
            assert d.visibility_reason is not None
        else:
            assert d.visibility_reason is None
    WorkspacePlanResponse.model_validate(response.model_dump())


def test_large_clinical_context_still_validates() -> None:
    meds = tuple(
        MedicationEvidence(medication_id=f"m{i}", name=f"Drug{i}") for i in range(40)
    )
    labs = tuple(
        LabEvidence(lab_id=f"l{i}", name=f"Lab{i}", extracted_data=f"value {i}")
        for i in range(30)
    )
    ctx = _context(
        medication_evidence=meds,
        lab_evidence=labs,
        timeline=_timeline(count=80),
        overview=MedicalOverview(
            allergies="Penicillin",
            current_medications=[
                CurrentMedication(id=f"m{i}", name=f"Drug{i}", amount="10mg", frequency="daily")
                for i in range(40)
            ],
            lab_results=[
                LabResult(id=f"l{i}", name=f"Lab{i}", extracted_data=f"value {i}")
                for i in range(30)
            ],
        ),
    )
    plan = _plan(ctx)
    response = to_workspace_plan_response(plan)
    assert response.cognitive_budget.primary_count >= 0
    assert response.cognitive_budget.deferred_count >= 0
    WorkspacePlan.model_validate(plan.model_dump())
    WorkspacePlanResponse.model_validate(response.model_dump())


def test_context_hash_stable_and_sensitive() -> None:
    ctx_a = _context()
    ctx_b = _context()
    assert compute_context_hash(ctx_a) == compute_context_hash(ctx_b)

    mutated = _context(
        summary=MedicalSummary(
            chief_complaint="Different complaint",
            extracted_at=FIXED_NOW,
        )
    )
    assert compute_context_hash(ctx_a) != compute_context_hash(mutated)

    plan = _plan(ctx_a)
    assert plan.metadata.context_hash == compute_context_hash(ctx_a)


def test_clinical_context_immutable_across_orchestration() -> None:
    ctx = _context()
    before = deepcopy(ctx.model_dump(mode="json"))
    plan = _plan(ctx)
    _ = to_workspace_plan_response(plan)
    assert ctx.model_dump(mode="json") == before


# ── Semantic invariants: Plan → DTO ──────────────────────────────────────────


def test_identity_invariant_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)

    plan_ids = [d.object_id.value for d in plan.layout_directives]
    dto_ids = [d.object_id for d in response.layout_directives]

    assert plan_ids == dto_ids
    assert set(dto_ids) == ALL_OBJECT_IDS
    assert len(dto_ids) == len(set(dto_ids))
    assert len(dto_ids) == len(ALL_OBJECT_IDS)


def test_priority_invariant_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    by_plan = {d.object_id.value: d.priority.value for d in plan.layout_directives}
    by_dto = {d.object_id: d.priority for d in response.layout_directives}
    assert by_plan == by_dto


def test_visibility_invariant_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    for domain_d, wire_d in zip(plan.layout_directives, response.layout_directives, strict=True):
        assert wire_d.object_id == domain_d.object_id.value
        assert wire_d.slot == domain_d.slot.value
        assert wire_d.pinned == domain_d.pinned
        expected_reason = (
            domain_d.visibility_reason.value if domain_d.visibility_reason is not None else None
        )
        assert wire_d.visibility_reason == expected_reason
        if domain_d.slot is AttentionSlot.HIDDEN:
            assert wire_d.slot == "hidden"
            assert wire_d.visibility_reason is not None


def test_trust_invariant_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    for domain_d, wire_d in zip(plan.layout_directives, response.layout_directives, strict=True):
        assert wire_d.trust.primary_provenance == domain_d.trust.primary_provenance.value
        assert wire_d.trust.all_provenance == [
            p.value for p in domain_d.trust.all_provenance
        ]
        assert wire_d.trust.verification == domain_d.trust.verification.value
        assert list(wire_d.trust.evidence_refs) == list(domain_d.trust.evidence_refs)
        if domain_d.trust.confidence == "unknown":
            assert wire_d.trust.confidence is None
        else:
            assert wire_d.trust.confidence == float(domain_d.trust.confidence)


def test_ordering_invariant_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)

    assert [d.object_id for d in response.layout_directives] == [
        d.object_id.value for d in plan.layout_directives
    ]
    assert response.pin_zone == [oid.value for oid in plan.pin_zone]
    assert [item.rank for item in response.decision_queue] == [
        item.rank for item in plan.decision_queue.items
    ]
    assert [item.object_id for item in response.decision_queue] == [
        item.object_id.value for item in plan.decision_queue.items
    ]


def test_story_narrative_preserved_plan_to_dto() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    if plan.story is None:
        assert response.story is None
    else:
        assert response.story is not None
        assert response.story.text == plan.story.text
        assert response.story.stale == plan.story.stale
        assert list(response.story.evidence_refs) == list(plan.story.evidence_refs)
