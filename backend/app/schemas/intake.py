import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    patient_questions: list[str] = Field(default_factory=list)


class ChronicCondition(BaseModel):
    id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1)
    duration: str = ""


class LabResult(BaseModel):
    id: str = Field(min_length=1, max_length=36)
    name: str = Field(min_length=1)
    extracted_data: str | None = None


class CurrentMedication(BaseModel):
    id: str = Field(min_length=1, max_length=36)
    name: str = ""
    amount: str = ""
    frequency: str = ""


class MedicalOverview(BaseModel):
    allergies: str = ""
    surgical_history: str = ""
    family_history: str = ""
    chronic_conditions: list[ChronicCondition] = Field(default_factory=list)
    current_medications: list[CurrentMedication] = Field(default_factory=list)
    lab_results: list[LabResult] = Field(default_factory=list)
    file_condition_map: dict[int, str] = Field(default_factory=dict)
    patient_questions: str | None = None

    @field_validator("current_medications", mode="before")
    @classmethod
    def coerce_current_medications(cls, value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        coerced: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                name = item.strip()
                if name:
                    coerced.append(
                        {
                            "id": str(uuid.uuid4()),
                            "name": name,
                            "amount": "",
                            "frequency": "",
                        }
                    )
            elif isinstance(item, dict):
                coerced.append(item)
            elif hasattr(item, "model_dump"):
                coerced.append(item.model_dump())
        return coerced

    @model_validator(mode="after")
    def validate_unique_condition_ids(self) -> "MedicalOverview":
        ids = [c.id for c in self.chronic_conditions]
        if len(ids) != len(set(ids)):
            raise ValueError("chronic_conditions must have unique ids")
        lab_ids = [lab.id for lab in self.lab_results]
        if len(lab_ids) != len(set(lab_ids)):
            raise ValueError("lab_results must have unique ids")
        med_ids = [med.id for med in self.current_medications]
        if len(med_ids) != len(set(med_ids)):
            raise ValueError("current_medications must have unique ids")
        return self


class ConditionFileRef(BaseModel):
    id: int
    filename: str
    mime_type: str | None
    url: str
    size_bytes: int
    condition_id: str | None = None


class ChronicConditionWithFiles(ChronicCondition):
    files: list[ConditionFileRef] = Field(default_factory=list)


class ClinicalOverviewResponse(BaseModel):
    hpi: str | None
    drug_history: list[str]
    allergies: str
    surgical_history: str
    family_history: str
    chronic_conditions: list[ChronicConditionWithFiles]
    unlinked_files: list[ConditionFileRef]


class IntakeResponse(BaseModel):
    id: int
    session_id: int
    current_layer: int
    session_initial_complaint: Optional[str] = None
    demographics: Optional[DemographicsInput] = None
    hpi_questions: Optional[HPIQuestionsResponse] = None
    hpi_answers: Optional[dict[str, str]] = None
    clinical_summary: Optional[ClinicalSummary] = None
    medical_overview: Optional[MedicalOverview] = None
    llm_fallback_used: bool = False
    llm_error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FileConditionLink(BaseModel):
    condition_id: str | None = None
