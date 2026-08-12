"""Wire DTOs for Workspace clinical content projection — presentation only."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTENT_VERSION = "1.0.0"

SeverityLevel = Literal["critical", "warning", "info"]
TrendDirection = Literal["up", "down", "stable", "unknown"]
ConfidenceValue = float | Literal["unknown"]


class PatientHeaderContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    age: int
    sex: str
    mrn: str
    visit_type: str
    status: str


class ChiefComplaintContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    duration: str
    priority: str


class RedFlagItemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    severity: SeverityLevel
    explanation: str


class RedFlagsContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[RedFlagItemDTO] = Field(default_factory=list)


class SnapshotStripContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    vitals: str
    problems: str
    risk: str
    allergies: str
    medication_count: int
    timeline_count: int


class TimelineEventDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    detail: str
    source: str


class TimelineGroupDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    date: str
    events: list[TimelineEventDTO] = Field(default_factory=list)


class TimelineContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    groups: list[TimelineGroupDTO] = Field(default_factory=list)


class MedicationItemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    dose: str
    frequency: str
    status: str
    source: str


class MedicationGroupDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    items: list[MedicationItemDTO] = Field(default_factory=list)


class MedicationsContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    groups: list[MedicationGroupDTO] = Field(default_factory=list)


class LabRowDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    value: str
    unit: str
    reference_range: str
    abnormal: bool
    trend: TrendDirection
    detail: str


class LabsContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: list[LabRowDTO] = Field(default_factory=list)


class MissingInfoItemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    priority: str


class MissingInfoContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[MissingInfoItemDTO] = Field(default_factory=list)
    action_label: str


class SoapContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    assessment: str
    plan: str


class DocumentItemDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    confidence: ConfidenceValue
    uploaded_at: str
    detail: str


class DocumentsContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[DocumentItemDTO] = Field(default_factory=list)


class ClinicalContentBodyDTO(BaseModel):
    """Presentation content payload — clinical/display fields only."""

    model_config = ConfigDict(frozen=True)

    patient_header: PatientHeaderContentDTO | None = None
    chief_complaint: ChiefComplaintContentDTO | None = None
    red_flags: RedFlagsContentDTO | None = None
    snapshot: SnapshotStripContentDTO | None = None
    timeline: TimelineContentDTO | None = None
    medications: MedicationsContentDTO | None = None
    labs: LabsContentDTO | None = None
    missing_info: MissingInfoContentDTO | None = None
    soap: SoapContentDTO | None = None
    documents: DocumentsContentDTO | None = None


class ClinicalContentResponse(BaseModel):
    """Versioned transport envelope for clinical content projection."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    context_hash: str
    content_version: str = CONTENT_VERSION
    generated_at: str
    content: ClinicalContentBodyDTO
