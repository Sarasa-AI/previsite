"""Wire DTOs for Workspace clinical content projection — presentation only."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CONTENT_VERSION = "1.0.0"

SeverityLevel = Literal["critical", "warning", "info"]
TrendDirection = Literal["up", "down", "stable", "unknown"]
AllergySemanticState = Literal["confirmed", "nkda", "unknown", "not_documented", "conflict"]
LabSemanticState = Literal["normal", "abnormal", "critical", "unknown"]
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


class HPIContentDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    hpi_summary: str


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
    allergy_state: AllergySemanticState
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
    catalog_id: int | None = None
    name: str
    dose: str
    dose_unit: str | None = None
    frequency: str
    status: str
    source: str
    generic_name: str | None = None
    brand_name: str | None = None
    strength: str | None = None
    dosage_form: str | None = None
    manufacturer: str | None = None
    company: str | None = None
    quantity: str | None = None
    duration: str | None = None
    route: str | None = None
    instructions: str | None = None
    confidence: float | None = None
    verification_status: str | None = None


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
    state: LabSemanticState
    trend: TrendDirection
    detail: str
    timestamp: str
    source: str


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
    hpi: HPIContentDTO | None = None
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
