"""TimelineBuilder — ClinicalContext → ClinicalTimeline (no diagnosis inference)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.modules.timeline.application.extractors import TimelineExtractors
from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventType,
    TemporalKind,
    TemporalStatus,
)
from app.modules.timeline.domain.models import ClinicalTimeline, TemporalEvidence, TimelineEvent
from app.modules.timeline.infrastructure.temporal_normalizer import TemporalNormalizer
from app.schemas.clinical_context import ClinicalContext

_SOURCE_PRIORITY = {
    "hpi": 0,
    "pmh": 1,
    "medication": 2,
    "laboratory": 3,
    "surgical_history": 4,
    "document": 5,
    "chat": 6,
    "other": 7,
}


def _sort_key(event: TimelineEvent, anchor_at: datetime) -> tuple:
    """Chronological key: known absolute first, unknowns last."""
    temporal = event.temporal
    if temporal.kind == TemporalKind.UNKNOWN or temporal.absolute_datetime is None:
        # Unknown chronology sorts last
        return (1, anchor_at, _SOURCE_PRIORITY.get(event.source.value, 99), event.label.lower())
    return (
        0,
        temporal.absolute_datetime,
        _SOURCE_PRIORITY.get(event.source.value, 99),
        event.label.lower(),
    )


def _derive_views(events: tuple[TimelineEvent, ...]) -> dict[str, tuple[str, ...]]:
    active: list[str] = []
    resolved: list[str] = []
    historical: list[str] = []
    medication_changes: list[str] = []
    laboratory_progression: list[str] = []
    unknown_chronology: list[str] = []

    for event in events:
        if event.temporal.kind == TemporalKind.UNKNOWN or event.temporal.absolute_datetime is None:
            if event.temporal.kind == TemporalKind.UNKNOWN:
                unknown_chronology.append(event.event_id)

        if event.status == TemporalStatus.ONGOING and event.clinical_category in {
            ClinicalCategory.SYMPTOM,
            ClinicalCategory.CONDITION,
        }:
            active.append(event.event_id)
        elif event.status == TemporalStatus.RESOLVED:
            resolved.append(event.event_id)
        elif event.status == TemporalStatus.HISTORICAL:
            historical.append(event.event_id)

        if event.event_type in {
            EventType.MEDICATION_START,
            EventType.MEDICATION_CHANGE,
            EventType.MEDICATION_STOP,
        }:
            medication_changes.append(event.event_id)

        if event.event_type == EventType.LAB_RESULT or event.clinical_category == ClinicalCategory.LABORATORY:
            laboratory_progression.append(event.event_id)

        # Recurring symptoms/conditions also count as active problems
        if event.status == TemporalStatus.RECURRING and event.clinical_category in {
            ClinicalCategory.SYMPTOM,
            ClinicalCategory.CONDITION,
        }:
            if event.event_id not in active:
                active.append(event.event_id)

    return {
        "active_problems": tuple(active),
        "resolved_problems": tuple(resolved),
        "historical_events": tuple(historical),
        "medication_changes": tuple(medication_changes),
        "laboratory_progression": tuple(laboratory_progression),
        "unknown_chronology": tuple(unknown_chronology),
    }


def _collect_evidence(events: tuple[TimelineEvent, ...]) -> tuple[TemporalEvidence, ...]:
    refs: list[TemporalEvidence] = []
    seen: set[tuple[str, str | None, str]] = set()
    for event in events:
        for evidence in event.evidence:
            key = (evidence.source.value, evidence.source_ref, evidence.excerpt)
            if key in seen:
                continue
            seen.add(key)
            refs.append(evidence)
    return tuple(refs)


class TimelineBuilder:
    """
    Build a ClinicalTimeline from ClinicalContext.

    Organizes temporal information only — does not infer diagnoses,
    rank diseases, or generate recommendations.
    """

    def __init__(
        self,
        normalizer: TemporalNormalizer | None = None,
        extractors: TimelineExtractors | None = None,
    ) -> None:
        self._normalizer = normalizer or TemporalNormalizer()
        self._extractors = extractors or TimelineExtractors(self._normalizer)

    def build(
        self,
        context: ClinicalContext,
        *,
        anchor_at: datetime | None = None,
    ) -> ClinicalTimeline:
        anchor = anchor_at or datetime.now(timezone.utc)
        if anchor.tzinfo is None:
            anchor = anchor.replace(tzinfo=timezone.utc)

        # Build against a context without an existing timeline to avoid recursion.
        base = context
        if context.timeline is not None:
            base = context.model_copy(update={"timeline": None})

        raw_events = self._extractors.extract_all(base, anchor_at=anchor)
        ordered = tuple(sorted(raw_events, key=lambda e: _sort_key(e, anchor)))
        views = _derive_views(ordered)

        return ClinicalTimeline(
            session_id=context.session_id,
            patient_id=context.patient_id,
            anchor_at=anchor,
            events=ordered,
            active_problems=views["active_problems"],
            resolved_problems=views["resolved_problems"],
            historical_events=views["historical_events"],
            medication_changes=views["medication_changes"],
            laboratory_progression=views["laboratory_progression"],
            unknown_chronology=views["unknown_chronology"],
            evidence_refs=_collect_evidence(ordered),
        )


timeline_builder = TimelineBuilder()
