from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.national_id import validate_iranian_national_id


class DemographicsInput(BaseModel):
    first_name: str
    last_name: str
    national_id: str
    insurance_provider: str
    age: int = Field(ge=0, le=150)
    sex: str
    weight: float = Field(gt=0)
    height: float = Field(gt=0)
    chief_complaint: str

    @field_validator("national_id")
    @classmethod
    def validate_national_id(cls, value: str) -> str:
        normalized = value.strip()
        if not validate_iranian_national_id(normalized):
            raise ValueError("INVALID_NATIONAL_ID")
        return normalized


class HPIQuestion(BaseModel):
    id: str
    question: str
    priority: int
    red_flag_related: bool = False


class HPIQuestionsResponse(BaseModel):
    question_strategy: str
    questions: list[HPIQuestion]


class HPIAnswerInput(BaseModel):
    question_id: str
    answer: str


class ClinicalSummary(BaseModel):
    chief_complaint: str
    hpi_summary: str
    pertinent_positives: list[str]
    pertinent_negatives: list[str]
    red_flags: list[str]


class MedicalHistoryInput(BaseModel):
    allergy_history: list[str] = Field(default_factory=list)
    past_medical_history: list[str] = Field(default_factory=list)
    past_surgical_history: list[str] = Field(default_factory=list)
    family_history: list[str] = Field(default_factory=list)


class IntakeResponse(BaseModel):
    id: int
    session_id: int
    current_layer: int
    demographics: Optional[DemographicsInput] = None
    hpi_questions: Optional[HPIQuestionsResponse] = None
    hpi_answers: Optional[dict[str, str]] = None
    clinical_summary: Optional[ClinicalSummary] = None
    medical_history: Optional[MedicalHistoryInput] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
