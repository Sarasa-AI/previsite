"""Clinical content projection tests — determinism, SoT, null handling."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

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
    TemporalEvidence,
    TemporalExpression,
    TimelineEvent,
)
from app.modules.workspace.application.projections.adapters import (
    ClinicalContentAdapters,
    DemographicsAdapter,
    DocumentAdapterItem,
    SessionAdapter,
    SoapAdapter,
)
from app.modules.workspace.application.projections.project_clinical_content import (
    project_clinical_content,
)
from app.modules.workspace.interface.clinical_content_dto import CONTENT_VERSION
from app.schemas.clinical_context import (
    ClinicalContext,
    LabEvidence,
    MedicationEvidence,
)
from app.schemas.intake import (
    ChronicCondition,
    CurrentMedication,
    LabResult,
    MedicalOverview,
)
from app.schemas.medical import MedicalSummary

FIXED_NOW = datetime(2026, 7, 28, 15, 0, 0, tzinfo=timezone.utc)
GENERATED_AT = "2026-07-28T15:00:00+00:00"


def _timeline(*labels: str, with_absolute: bool = False) -> ClinicalTimeline:
    events = []
    for i, label in enumerate(labels):
        absolute = None
        kind = TemporalKind.RELATIVE_DURATION
        if with_absolute:
            absolute = datetime(2026, 7, 20 + i, 12, 0, 0, tzinfo=timezone.utc)
            kind = TemporalKind.ABSOLUTE
        events.append(
            TimelineEvent(
                event_id=f"e{i}",
                event_type=EventType.SYMPTOM_ONGOING,
                clinical_category=ClinicalCategory.SYMPTOM,
                label=label,
                temporal=TemporalExpression(
                    kind=kind,
                    raw_text="2 days",
                    absolute_datetime=absolute,
                    relative_value=2,
                    relative_unit="days",
                    precision=TemporalPrecision.DAY,
                    uncertainty=False,
                ),
                status=TemporalStatus.ONGOING,
                source=EventSource.HPI,
                evidence=(
                    TemporalEvidence(
                        source=EventSource.HPI,
                        excerpt=f"excerpt for {label}",
                        confidence=1.0,
                    ),
                ),
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
            symptom_duration="2 days",
            allergies=["Penicillin"],
            current_medications=["Metformin 500mg"],
            additional_notes=(
                "HPI text\n"
                "Red flags: Chest pain; Syncope\n"
                "Pertinent positives: Photophobia"
            ),
            is_hpi_complete=True,
            extracted_at=FIXED_NOW,
        ),
        "overview": MedicalOverview(
            allergies="Penicillin",
            chronic_conditions=[
                ChronicCondition(id="c1", name="HTN", duration="5y"),
                ChronicCondition(id="c2", name="T2DM", duration="3y"),
            ],
            current_medications=[
                CurrentMedication(
                    id="m1", name="Metformin", amount="500mg", frequency="BID"
                )
            ],
            lab_results=[
                LabResult(
                    id="l1", name="BMP", extracted_data="Potassium 6.5 mEq/L critical"
                )
            ],
        ),
        "lab_evidence": (
            LabEvidence(
                lab_id="l1", name="BMP", extracted_data="Potassium 6.5 critical"
            ),
        ),
        "medication_evidence": (
            MedicationEvidence(
                medication_id="m1",
                name="Metformin",
                amount="500mg",
                frequency="BID",
            ),
        ),
        "timeline": _timeline("Headache onset", "Nausea", with_absolute=True),
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _adapters(**overrides) -> ClinicalContentAdapters:
    base = {
        "session": SessionAdapter(
            session_id=1,
            status="active",
            visit_type="Follow-up",
            generated_at=GENERATED_AT,
        ),
        "demographics": DemographicsAdapter(
            first_name="Jane",
            last_name="Doe",
            age=54,
            sex="female",
            national_id="MRN-10042",
        ),
        "documents": (
            DocumentAdapterItem(
                file_id=10,
                filename="labs.pdf",
                uploaded_at="2026-07-27T10:00:00+00:00",
                detail="",
            ),
        ),
        "soap": SoapAdapter(
            soap_note=(
                "**A - Assessment (ارزیابی)**\nPossible migraine.\n\n"
                "**P - Plan (برنامه)**\nFollow up in 1 week."
            ),
            soap_status="ready",
        ),
    }
    base.update(overrides)
    return ClinicalContentAdapters(**base)


def test_full_projection_populates_all_slices():
    response = project_clinical_content(_context(), _adapters())
    assert response.session_id == 1
    assert response.content_version == CONTENT_VERSION
    assert response.generated_at == GENERATED_AT
    assert response.context_hash
    content = response.content
    assert content.patient_header is not None
    assert content.patient_header.name == "Jane Doe"
    assert content.chief_complaint is not None
    assert content.chief_complaint.title == "Headache for two days"
    assert content.chief_complaint.duration == "2 days"
    assert content.red_flags is not None
    assert [i.title for i in content.red_flags.items] == ["Chest pain", "Syncope"]
    assert content.red_flags.items[0].severity == "critical"
    assert content.snapshot is not None
    assert "HTN" in content.snapshot.problems
    assert content.snapshot.medication_count == 1
    assert content.snapshot.timeline_count == 2
    assert content.timeline is not None
    assert len(content.timeline.groups) == 2
    assert content.medications is not None
    assert content.medications.groups[0].items[0].name == "Metformin"
    assert content.labs is not None
    assert content.labs.rows[0].abnormal is True
    assert content.missing_info is None
    assert content.soap is not None
    assert "migraine" in content.soap.assessment.lower()
    assert content.documents is not None
    assert content.documents.items[0].name == "labs.pdf"


def test_empty_context_yields_null_clinical_slices():
    ctx = ClinicalContext(
        session_id=1,
        patient_id=7,
        summary=MedicalSummary(extracted_at=FIXED_NOW, is_hpi_complete=False),
    )
    adapters = ClinicalContentAdapters(
        session=SessionAdapter(session_id=1, generated_at=GENERATED_AT),
    )
    response = project_clinical_content(ctx, adapters)
    content = response.content
    assert content.patient_header is None
    assert content.chief_complaint is None
    assert content.red_flags is None
    assert content.timeline is None
    assert content.medications is None
    assert content.labs is None
    assert content.documents is None
    assert content.soap is None
    # Missing info present for absent CC / allergies / meds / incomplete HPI
    assert content.missing_info is not None
    ids = {item.id for item in content.missing_info.items}
    assert "missing-chief-complaint" in ids
    assert "missing-allergies" in ids


def test_partial_projection_chief_complaint_only():
    ctx = ClinicalContext(
        session_id=1,
        patient_id=7,
        summary=MedicalSummary(
            chief_complaint="Fatigue",
            allergies=["NKDA"],
            is_hpi_complete=True,
            extracted_at=FIXED_NOW,
        ),
    )
    response = project_clinical_content(ctx, _adapters(demographics=None, documents=(), soap=None))
    assert response.content.chief_complaint is not None
    assert response.content.chief_complaint.title == "Fatigue"
    assert response.content.patient_header is None
    assert response.content.documents is None
    assert response.content.soap is None
    assert response.content.red_flags is None


def test_determinism_identical_inputs_identical_response():
    ctx = _context()
    adapters = _adapters()
    a = project_clinical_content(ctx, adapters)
    b = project_clinical_content(ctx, adapters)
    assert a.model_dump(mode="json") == b.model_dump(mode="json")


def test_single_clinical_change_only_expected_delta():
    base_ctx = _context()
    adapters = _adapters()
    before = project_clinical_content(base_ctx, adapters)

    changed = _context(
        summary=MedicalSummary(
            chief_complaint="Chest tightness",
            symptom_duration="2 days",
            allergies=["Penicillin"],
            current_medications=["Metformin 500mg"],
            additional_notes=base_ctx.summary.additional_notes,
            is_hpi_complete=True,
            extracted_at=FIXED_NOW,
        )
    )
    after = project_clinical_content(changed, adapters)

    before_dump = before.model_dump(mode="json")
    after_dump = after.model_dump(mode="json")

    assert before_dump["content"]["chief_complaint"] != after_dump["content"]["chief_complaint"]
    assert before_dump["context_hash"] != after_dump["context_hash"]

    # Other clinical slices unchanged except snapshot may share CC-driven presence
    assert before_dump["content"]["red_flags"] == after_dump["content"]["red_flags"]
    assert before_dump["content"]["medications"] == after_dump["content"]["medications"]
    assert before_dump["content"]["labs"] == after_dump["content"]["labs"]
    assert before_dump["content"]["timeline"] == after_dump["content"]["timeline"]
    assert before_dump["content"]["documents"] == after_dump["content"]["documents"]
    assert before_dump["content"]["soap"] == after_dump["content"]["soap"]
    assert before_dump["content"]["patient_header"] == after_dump["content"]["patient_header"]


def test_red_flags_come_from_clinical_context_not_adapters():
    ctx = _context(
        summary=MedicalSummary(
            chief_complaint="Headache",
            additional_notes="Red flags: Bleeding",
            allergies=["NKDA"],
            is_hpi_complete=True,
            extracted_at=FIXED_NOW,
        )
    )
    response = project_clinical_content(ctx, _adapters())
    assert response.content.red_flags is not None
    assert response.content.red_flags.items[0].title == "Bleeding"


def test_medications_prefer_clinical_context_evidence():
    ctx = _context()
    response = project_clinical_content(ctx, _adapters())
    items = response.content.medications.groups[0].items
    assert items[0].id == "m1"
    assert items[0].source == "clinical_context"


def test_timeline_groups_sorted_deterministically():
    ctx = _context(timeline=_timeline("B", "A", with_absolute=True))
    response = project_clinical_content(ctx, _adapters())
    groups = response.content.timeline.groups
    dates = [g.date for g in groups]
    assert dates == sorted(dates)
    for group in groups:
        ids = [e.id for e in group.events]
        assert ids == sorted(ids)


def test_response_has_no_domain_type_names_in_json():
    dump = project_clinical_content(_context(), _adapters()).model_dump_json()
    assert "ClinicalContext" not in dump
    assert "TimelineEvent" not in dump
    assert "MedicalSummary" not in dump
    assert "EventSource" not in dump


def test_soap_fallback_when_sections_missing():
    adapters = _adapters(
        soap=SoapAdapter(soap_note="Unstructured note without sections.", soap_status="ready")
    )
    response = project_clinical_content(_context(), adapters)
    assert response.content.soap is not None
    assert response.content.soap.assessment == "Unstructured note without sections."
    assert response.content.soap.plan == ""
