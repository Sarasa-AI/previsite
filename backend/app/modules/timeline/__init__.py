"""Clinical Timeline Engine — chronology from ClinicalContext without diagnosis inference."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.modules.timeline.domain.enums import (
    ClinicalCategory,
    EventSource,
    EventType,
    RelationType,
    TemporalKind,
    TemporalPrecision,
    TemporalStatus,
)
from app.modules.timeline.domain.models import (
    ClinicalTimeline,
    EventRelation,
    TemporalEvidence,
    TemporalExpression,
    TimelineEvent,
)

if TYPE_CHECKING:
    from app.modules.timeline.application.timeline_builder import TimelineBuilder as TimelineBuilder

__all__ = [
    "ClinicalCategory",
    "ClinicalTimeline",
    "EventRelation",
    "EventSource",
    "EventType",
    "RelationType",
    "TemporalEvidence",
    "TemporalExpression",
    "TemporalKind",
    "TemporalPrecision",
    "TemporalStatus",
    "TimelineBuilder",
    "TimelineEvent",
]


def __getattr__(name: str):
    if name == "TimelineBuilder":
        from app.modules.timeline.application.timeline_builder import TimelineBuilder

        return TimelineBuilder
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
