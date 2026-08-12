"""Workspace interface layer tests — DTO validation and one-way mappers."""

from __future__ import annotations

import hashlib
import importlib
import inspect
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
from app.modules.workspace.interface.dto import (
    CONTRACT_VERSION,
    AcknowledgementRequest,
    WorkspacePlanResponse,
)
from app.modules.workspace.interface.mappers import (
    compute_plan_etag,
    confidence_to_wire,
    format_utc_z,
    to_decision_trace_response,
    to_workspace_plan_response,
)

NOW = datetime(2026, 7, 28, 14, 30, 0, tzinfo=timezone.utc)


def _trust(**overrides) -> TrustDescriptor:
    base = {
        "primary_provenance": TrustProvenance.SYSTEM_DERIVED,
        "all_provenance": (TrustProvenance.SYSTEM_DERIVED,),
        "confidence": 1.0,
        "verification": TrustVerification.NA,
        "evidence_refs": ("overview.allergies",),
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
        "flags": (),
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


def _plan(**overrides) -> WorkspacePlan:
    cc = _directive()
    labs = _directive(
        object_id=ClinicalObjectId.LABS,
        priority=PriorityLevel.P3,
        slot=AttentionSlot.HIDDEN,
        size=SizeHint.COMPRESSED,
        pinned=False,
        visibility_reason=VisibilityReason.NO_DATA,
        trust=_trust(confidence="unknown"),
        flags=("acknowledge_required",),
    )
    queue = DecisionQueue(
        items=(
            DecisionQueueItem(
                rank=1,
                object_id=ClinicalObjectId.CHIEF_COMPLAINT,
                reason_code=ReasonCode.ORIENT,
                explanation="Visit orientation: chief complaint",
                acknowledge_required=False,
            ),
        )
    )
    story = ClinicalStory(
        text="Patient presents with headache.",
        confidence=0.8,
        evidence_refs=("summary.chief_complaint",),
        stale=False,
    )
    trace = DecisionTrace(
        steps=(
            DecisionTraceStep(
                object_id=ClinicalObjectId.CHIEF_COMPLAINT,
                step_label="base_priority",
                priority_before=None,
                priority_after=PriorityLevel.P1,
                detail="Default P1 when present",
            ),
        )
    )
    base = {
        "session_id": 42,
        "workspace_state": WorkspaceState.REVIEW_NEEDED,
        "layout_directives": (cc, labs),
        "decision_queue": queue,
        "story": story,
        "pin_zone": (ClinicalObjectId.CHIEF_COMPLAINT,),
        "cognitive_budget": _budget(),
        "decision_trace": trace,
        "metadata": _metadata(),
    }
    base.update(overrides)
    return WorkspacePlan(**base)


# ── Round-trip shape ─────────────────────────────────────────────────────────


def test_workspace_plan_response_shape_excludes_decision_trace() -> None:
    response = to_workspace_plan_response(_plan())
    dump = response.model_dump()

    assert set(dump.keys()) == {
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
    assert "decision_trace" not in dump
    assert response.session_id == 42
    assert response.workspace_state == "review_needed"
    assert len(response.layout_directives) == 2
    assert len(response.decision_queue) == 1
    assert response.story is not None
    assert response.pin_zone == ["chief_complaint"]


# ── Wire transforms ──────────────────────────────────────────────────────────


def test_unknown_confidence_maps_to_null() -> None:
    assert confidence_to_wire("unknown") is None
    assert confidence_to_wire(0.75) == 0.75

    response = to_workspace_plan_response(_plan())
    labs = next(d for d in response.layout_directives if d.object_id == "labs")
    assert labs.trust.confidence is None
    assert labs.visibility_reason == "no_data"
    assert labs.flags == ["acknowledge_required"]


def test_timestamps_use_iso8601_utc_z() -> None:
    assert format_utc_z(NOW) == "2026-07-28T14:30:00Z"
    naive = datetime(2026, 7, 28, 14, 30, 0)
    assert format_utc_z(naive) == "2026-07-28T14:30:00Z"

    response = to_workspace_plan_response(_plan())
    assert response.metadata.computed_at == "2026-07-28T14:30:00Z"
    assert response.metadata.generated_at.endswith("Z")


def test_enums_and_tuples_serialize_as_wire_strings_and_lists() -> None:
    response = to_workspace_plan_response(_plan())
    assert response.decision_queue[0].reason_code == "ORIENT"
    assert response.decision_queue[0].object_id == "chief_complaint"
    assert isinstance(response.pin_zone, list)
    assert isinstance(response.layout_directives[0].trust.all_provenance, list)
    assert response.metadata.lens == "general_medicine"
    assert response.metadata.role == "doctor"


def test_null_story_when_absent() -> None:
    response = to_workspace_plan_response(_plan(story=None))
    assert response.story is None


# ── Wire-only fields ─────────────────────────────────────────────────────────


def test_contract_version_and_plan_etag() -> None:
    assert CONTRACT_VERSION == "1.0.0"
    plan = _plan()
    response = to_workspace_plan_response(
        plan, acknowledgement_state_version="ack-v1"
    )
    assert response.contract_version == "1.0.0"
    expected = compute_plan_etag(
        context_hash=plan.metadata.context_hash,
        workspace_plan_version=plan.metadata.workspace_plan_version,
        contract_version=CONTRACT_VERSION,
        lens="general_medicine",
        role="doctor",
        acknowledgement_state_version="ack-v1",
    )
    assert response.plan_etag == expected


# ── ETag canonicalization ────────────────────────────────────────────────────


def test_etag_identical_for_same_canonical_inputs() -> None:
    kwargs = dict(
        context_hash="h1",
        workspace_plan_version="1.0.0",
        contract_version="1.0.0",
        lens="general_medicine",
        role="doctor",
        acknowledgement_state_version="0",
    )
    assert compute_plan_etag(**kwargs) == compute_plan_etag(**kwargs)


def test_etag_changes_when_any_single_component_changes() -> None:
    base = dict(
        context_hash="h1",
        workspace_plan_version="1.0.0",
        contract_version="1.0.0",
        lens="general_medicine",
        role="doctor",
        acknowledgement_state_version="0",
    )
    baseline = compute_plan_etag(**base)
    mutations = {
        "context_hash": "h2",
        "workspace_plan_version": "1.0.1",
        "contract_version": "1.1.0",
        "lens": "cardiology",
        "role": "nurse",
        "acknowledgement_state_version": "1",
    }
    for key, value in mutations.items():
        changed = {**base, key: value}
        assert compute_plan_etag(**changed) != baseline, f"etag unchanged for {key}"


def test_etag_uses_pipe_separated_canonicalization() -> None:
    """Bare concatenation must not match; pipe-joined payload is authoritative."""
    components = [
        "abc",
        "1.0.0",
        "1.0.0",
        "general_medicine",
        "doctor",
        "0",
    ]
    pipe_payload = "|".join(components)
    bare_payload = "".join(components)

    expected = hashlib.sha256(pipe_payload.encode("utf-8")).hexdigest()
    bare = hashlib.sha256(bare_payload.encode("utf-8")).hexdigest()

    actual = compute_plan_etag(
        context_hash="abc",
        workspace_plan_version="1.0.0",
        contract_version="1.0.0",
        lens="general_medicine",
        role="doctor",
        acknowledgement_state_version="0",
    )
    assert actual == expected
    assert actual != bare


# ── Trace mapper ─────────────────────────────────────────────────────────────


def test_decision_trace_response_maps_steps() -> None:
    plan = _plan()
    response = to_workspace_plan_response(plan)
    trace = to_decision_trace_response(plan, response.plan_etag)

    assert trace.session_id == 42
    assert trace.plan_etag == response.plan_etag
    assert trace.trace_version == "1.0.0"
    assert len(trace.steps) == 1
    assert trace.steps[0].object_id == "chief_complaint"
    assert trace.steps[0].priority_before is None
    assert trace.steps[0].priority_after == "p1"
    dump = trace.model_dump()
    assert "chief_complaint" in str(dump)
    # No clinical aggregate / patient content keys
    assert "ClinicalContext" not in dump
    assert "overview" not in dump
    assert "pmh_assertions" not in dump


def test_decision_trace_empty_when_absent() -> None:
    plan = _plan(decision_trace=None)
    response = to_workspace_plan_response(plan)
    trace = to_decision_trace_response(plan, response.plan_etag)
    assert trace.steps == []
    assert trace.session_id == plan.session_id


# ── DTO validation ───────────────────────────────────────────────────────────


def test_acknowledgement_request_rejects_empty_object_id() -> None:
    with pytest.raises(ValidationError):
        AcknowledgementRequest(object_id="")
    assert AcknowledgementRequest(object_id="conflicts").object_id == "conflicts"


def test_response_dto_accepts_mapped_payload() -> None:
    response = to_workspace_plan_response(_plan())
    round_trip = WorkspacePlanResponse.model_validate(response.model_dump())
    assert round_trip.plan_etag == response.plan_etag
    assert round_trip.contract_version == CONTRACT_VERSION


# ── Boundary ─────────────────────────────────────────────────────────────────


def test_mappers_do_not_import_clinical_context() -> None:
    module = importlib.import_module("app.modules.workspace.interface.mappers")
    source = inspect.getsource(module)
    assert "ClinicalContext" not in source
    assert "clinical_context" not in source


def test_mapped_dump_has_no_clinical_context_keys() -> None:
    dump = to_workspace_plan_response(_plan()).model_dump()
    flat = str(dump)
    assert "ClinicalContext" not in flat
    assert "pmh_assertions" not in dump
    assert "lab_evidence" not in dump
    assert "medication_evidence" not in dump
    assert "file_analyses" not in dump
