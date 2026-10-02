"""Immutable Clinical Timeline domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    RelationType,
    TemporalKind,
    TemporalPrecision,
    TemporalStatus,
)

RelativeUnit = Literal["days", "weeks", "months", "years"]


class TemporalExpression(BaseModel):
    """Structured temporal expression — never flattened to prose alone."""

    model_config = ConfigDict(frozen=True)

    kind: TemporalKind
    raw_text: str
    absolute_datetime: datetime | None = None
    relative_value: int | None = None
    relative_unit: RelativeUnit | None = None
    precision: TemporalPrecision = TemporalPrecision.UNKNOWN
    uncertainty: bool = True
    recurring: bool = False


class TemporalEvidence(BaseModel):
    """Source pointer for a timeline event."""

    model_config = ConfigDict(frozen=True)

    source: EventSource
    source_ref: str | None = None
    excerpt: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class EventRelation(BaseModel):
    """Typed link between timeline events."""

    model_config = ConfigDict(frozen=True)

    relation_type: RelationType
    target_event_id: str


class TimelineEvent(BaseModel):
    """One clinical chronological atom."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: EventType
    clinical_category: ClinicalCategory
    label: str
    temporal: TemporalExpression
    status: TemporalStatus
    source: EventSource
    evidence: tuple[TemporalEvidence, ...] = ()
    relationships: tuple[EventRelation, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ClinicalTimeline(BaseModel):
    """
    Ordered clinical chronology derived from ClinicalContext.

    First derived clinical artifact (see docs/adr/0001-clinical-artifacts-aggregate.md).
    """

    model_config = ConfigDict(frozen=True)

    session_id: int
    patient_id: int
    anchor_at: datetime
    events: tuple[TimelineEvent, ...] = ()
    active_problems: tuple[str, ...] = ()
    resolved_problems: tuple[str, ...] = ()
    historical_events: tuple[str, ...] = ()
    medication_changes: tuple[str, ...] = ()
    laboratory_progression: tuple[str, ...] = ()
    unknown_chronology: tuple[str, ...] = ()
    evidence_refs: tuple[TemporalEvidence, ...] = ()
