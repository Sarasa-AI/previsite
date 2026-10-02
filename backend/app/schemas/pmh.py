from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, RootModel

from app.schemas.intake import MedicalOverview


class PhysicianMetadata(BaseModel):
    concept: str
    icd10_hint: str | None = None
    snomed_ct: str | None = None


class ConditionalFollowup(BaseModel):
    id: str
    ui_type: str
    patient_text: str
    physician_metadata: str


class PMHQuestion(BaseModel):
    id: str
    category: str
    subcategory: str
    priority: int
    ui_type: str
    patient_text: str
    physician_metadata: PhysicianMetadata
    conditional_followups: list[ConditionalFollowup] = Field(default_factory=list)


class PMHCategory(BaseModel):
    category_id: str
    farsi_title: str
    master_patient_text: str
    questions: list[PMHQuestion]


class PMHSchemaResponse(RootModel[list[PMHCategory]]):
    """Typed wrapper so OpenAPI names the response; serializes as a root JSON array."""


class PMHAnswer(BaseModel):
    category_id: str
    is_selected: bool
    question_responses: dict[str, str | bool]


class PMHSubmission(BaseModel):
    patient_id: int
    answers: list[PMHAnswer]


class PMHSubmissionResponse(BaseModel):
    patient_id: int
    last_updated: datetime
    answer_count: int


class PatientOverviewSubmission(BaseModel):
    patient_id: int
    overview: MedicalOverview


class PatientOverviewResponse(BaseModel):
    patient_id: int
    overview: MedicalOverview | None
    last_updated: datetime | None


class PMHAssertion(BaseModel):
    assertion_id: str
    concept: str
    subcategory: str | None = None
    category_id: str
    polarity: Literal["present", "category_denied"]
    source: Literal["questionnaire"] = "questionnaire"
    detail: str | None = None


class ClinicalDiscrepancy(BaseModel):
    pmh_assertion_id: str
    concept: str
    pmh_polarity: Literal["present", "category_denied"]
    chat_polarity: Literal["affirm", "deny"]
    chat_quote: str
    confidence: Literal["high", "low"]
