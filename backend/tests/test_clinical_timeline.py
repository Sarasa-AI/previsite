"""Clinical Timeline Engine scenario tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.modules.timeline.application.timeline_builder import TimelineBuilder
from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventType,
    TemporalKind,
    TemporalStatus,
)
from app.modules.timeline.domain.models import ClinicalTimeline
from app.schemas.clinical_context import ClinicalContext, LabEvidence, MedicationEvidence
from app.schemas.intake import ChronicCondition, MedicalOverview
from app.schemas.medical import MedicalSummary

ANCHOR = datetime(2026, 7, 24, 12, 0, 0, tzinfo=timezone.utc)


def _ctx(**overrides) -> ClinicalContext:
    base = {
        "session_id": 42,
        "patient_id": 7,
        "summary": MedicalSummary(chief_complaint="unspecified"),
    }
    base.update(overrides)
    return ClinicalContext(**base)


def _build(ctx: ClinicalContext) -> ClinicalTimeline:
    return TimelineBuilder().build(ctx, anchor_at=ANCHOR)


def test_headache_for_three_days_ongoing_symptom() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Headache for three days",
            symptom_duration="three days",
        )
    )
    timeline = _build(ctx)
    symptoms = [
        e
        for e in timeline.events
        if e.clinical_category == ClinicalCategory.SYMPTOM
        and "headache" in e.label.lower()
    ]
    assert symptoms, "expected ongoing headache symptom"
    event = symptoms[0]
    assert event.event_type == EventType.SYMPTOM_ONGOING
    assert event.status == TemporalStatus.ONGOING
    assert event.temporal.kind == TemporalKind.RELATIVE_DURATION
    assert event.temporal.relative_value == 3
    assert event.event_id in timeline.active_problems


def test_diabetes_diagnosed_2018_historical() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Follow-up",
            past_medical_history=["Diabetes diagnosed in 2018"],
        )
    )
    timeline = _build(ctx)
    diabetes = [e for e in timeline.events if "diabetes" in e.label.lower()]
    assert diabetes
    event = diabetes[0]
    assert event.event_type == EventType.CONDITION_DIAGNOSED
    assert event.status == TemporalStatus.HISTORICAL
    assert event.temporal.kind == TemporalKind.ABSOLUTE
    assert event.temporal.absolute_datetime is not None
    assert event.temporal.absolute_datetime.year == 2018
    assert event.event_id in timeline.historical_events


def test_medication_started_last_month() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Medication review",
            current_medications=["Metformin started last month"],
        )
    )
    timeline = _build(ctx)
    meds = [
        e
        for e in timeline.events
        if e.clinical_category == ClinicalCategory.MEDICATION
        and "metformin" in e.label.lower()
    ]
    assert meds
    event = meds[0]
    assert event.event_type == EventType.MEDICATION_START
    assert event.temporal.kind == TemporalKind.RELATIVE_PAST
    assert event.temporal.relative_unit == "months"
    assert event.event_id in timeline.medication_changes


def test_lab_uploaded_yesterday() -> None:
    ctx = _ctx(
        summary=MedicalSummary(chief_complaint="Lab review"),
        lab_evidence=(
            LabEvidence(
                lab_id="lab1",
                name="CBC",
                extracted_data="CBC panel uploaded yesterday",
            ),
        ),
    )
    timeline = _build(ctx)
    labs = [e for e in timeline.events if e.event_type == EventType.LAB_RESULT]
    assert labs
    event = labs[0]
    assert event.temporal.kind == TemporalKind.YESTERDAY
    assert event.event_id in timeline.laboratory_progression
    assert event.temporal.absolute_datetime is not None
    assert (ANCHOR - event.temporal.absolute_datetime).days == 1


def test_unknown_surgery_date() -> None:
    ctx = _ctx(
        summary=MedicalSummary(chief_complaint="Pre-op"),
        overview=MedicalOverview(surgical_history="Appendectomy date unknown"),
    )
    timeline = _build(ctx)
    procedures = [e for e in timeline.events if e.event_type == EventType.PROCEDURE]
    assert procedures
    event = procedures[0]
    assert "appendectomy" in event.label.lower() or "unknown" in event.label.lower()
    assert event.temporal.kind == TemporalKind.UNKNOWN
    assert event.event_id in timeline.unknown_chronology


def test_mixed_absolute_and_relative_ordering() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Headache for 2 days",
            symptom_duration="2 days",
            past_medical_history=["Hypertension diagnosed in 2015"],
            current_medications=["Lisinopril started last month"],
        )
    )
    timeline = _build(ctx)
    dated = [e for e in timeline.events if e.temporal.absolute_datetime is not None]
    times = [e.temporal.absolute_datetime for e in dated]
    assert times == sorted(times), "dated events must be chronologically ordered"


def test_multiple_recurring_events() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Migraine",
            symptoms=["Migraine every week", "Palpitations every week"],
            symptom_timing="every week",
        ),
        overview=MedicalOverview(
            chronic_conditions=[
                ChronicCondition(id="c1", name="Seasonal allergies", duration="every year"),
            ]
        ),
    )
    timeline = _build(ctx)
    recurring = [e for e in timeline.events if e.status == TemporalStatus.RECURRING]
    # At least migraine/palpitations/allergies should pick up recurring cues
    assert len(recurring) >= 2


def test_builder_does_not_invent_diagnoses() -> None:
    ctx = _ctx(
        summary=MedicalSummary(
            chief_complaint="Headache for three days",
            symptom_duration="three days",
        )
    )
    timeline = _build(ctx)
    labels = " ".join(e.label.lower() for e in timeline.events)
    # Must not invent DDx labels like migraine, tension headache, SAH
    assert "subarachnoid" not in labels
    assert "intracranial" not in labels
    assert any("headache" in e.label.lower() for e in timeline.events)


def test_timeline_models_are_immutable() -> None:
    ctx = _ctx(summary=MedicalSummary(chief_complaint="Pain for 1 day", symptom_duration="1 day"))
    timeline = _build(ctx)
    assert timeline.events
    event = timeline.events[0]
    with pytest.raises(ValidationError):
        event.label = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        timeline.session_id = 99  # type: ignore[misc]


def test_clinical_context_timeline_field_additive() -> None:
    ctx = _ctx(summary=MedicalSummary(chief_complaint="Cough for 5 days", symptom_duration="5 days"))
    assert ctx.timeline is None
    timeline = _build(ctx)
    attached = ctx.model_copy(update={"timeline": timeline})
    assert attached.timeline is not None
    assert isinstance(attached.timeline, ClinicalTimeline)
    assert attached.timeline.session_id == 42
    assert len(attached.timeline.events) >= 1


def test_evidence_refs_populated() -> None:
    ctx = _ctx(
        summary=MedicalSummary(chief_complaint="Fever for 2 days", symptom_duration="2 days")
    )
    timeline = _build(ctx)
    assert timeline.evidence_refs
    assert all(e.excerpt for e in timeline.evidence_refs)


def test_medication_evidence_path() -> None:
    ctx = _ctx(
        summary=MedicalSummary(chief_complaint="Meds"),
        medication_evidence=(
            MedicationEvidence(
                medication_id="m1",
                name="Atorvastatin started last month",
                amount="20mg",
                frequency="daily",
            ),
        ),
    )
    timeline = _build(ctx)
    meds = [e for e in timeline.events if "atorvastatin" in e.label.lower()]
    assert meds
    assert meds[0].event_id in timeline.medication_changes


def test_pmh_chronic_condition_duration() -> None:
    ctx = _ctx(
        summary=MedicalSummary(chief_complaint="Checkup"),
        overview=MedicalOverview(
            chronic_conditions=[
                ChronicCondition(id="c1", name="Diabetes", duration="۵ سال"),
            ]
        ),
    )
    timeline = _build(ctx)
    diabetes = [e for e in timeline.events if "diabetes" in e.label.lower()]
    assert diabetes
    assert diabetes[0].temporal.kind == TemporalKind.RELATIVE_DURATION
    assert diabetes[0].temporal.relative_value == 5
