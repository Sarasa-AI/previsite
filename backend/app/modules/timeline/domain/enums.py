"""Timeline domain enumerations (explicit temporal uncertainty)."""

from __future__ import annotations

from enum import Enum


class EventType(str, Enum):
    SYMPTOM_ONSET = "symptom_onset"
    SYMPTOM_ONGOING = "symptom_ongoing"
    CONDITION_DIAGNOSED = "condition_diagnosed"
    MEDICATION_START = "medication_start"
    MEDICATION_CHANGE = "medication_change"
    MEDICATION_STOP = "medication_stop"
    LAB_RESULT = "lab_result"
    PROCEDURE = "procedure"
    DOCUMENT_UPLOAD = "document_upload"
    NARRATIVE = "narrative"
    UNKNOWN = "unknown"


class ClinicalCategory(str, Enum):
    SYMPTOM = "symptom"
    CONDITION = "condition"
    MEDICATION = "medication"
    LABORATORY = "laboratory"
    PROCEDURE = "procedure"
    ALLERGY = "allergy"
    CHAT = "chat"
    DOCUMENT = "document"
    OTHER = "other"


class TemporalKind(str, Enum):
    ABSOLUTE = "absolute"
    TODAY = "today"
    YESTERDAY = "yesterday"
    RELATIVE_PAST = "relative_past"
    RELATIVE_DURATION = "relative_duration"
    RELATIVE_SINCE = "relative_since"
    APPROXIMATE = "approximate"
    UNKNOWN = "unknown"


class TemporalPrecision(str, Enum):
    EXACT = "exact"
    DAY = "day"
    MONTH = "month"
    YEAR = "year"
    APPROXIMATE = "approximate"
    RELATIVE = "relative"
    UNKNOWN = "unknown"


class TemporalStatus(str, Enum):
    ONGOING = "ongoing"
    RESOLVED = "resolved"
    HISTORICAL = "historical"
    RECURRING = "recurring"
    UNKNOWN = "unknown"


class EventSource(str, Enum):
    HPI = "hpi"
    PMH = "pmh"
    MEDICATION = "medication"
    LABORATORY = "laboratory"
    CHAT = "chat"
    DOCUMENT = "document"
    SURGICAL_HISTORY = "surgical_history"
    OTHER = "other"


class RelationType(str, Enum):
    SAME_PROBLEM = "same_problem"
    PRECEDES = "precedes"
    FOLLOWS = "follows"
    RELATED_TO = "related_to"
