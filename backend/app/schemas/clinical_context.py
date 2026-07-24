from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.timeline.domain.models import ClinicalTimeline
from app.schemas.intake import MedicalOverview
from app.schemas.medical import MedicalSummary
from app.schemas.pmh import PMHAnswer, PMHAssertion


class ClinicalChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    content: str
    created_at: datetime | None = None


class LabResultEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    test_name: str
    value: str | None = None
    unit: str | None = None


class MedicationEvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    dose: str | None = None
    frequency: str | None = None


class LabEvidence(BaseModel):
    """Structured lab evidence for Clinical AI modules (Lab Intelligence, SOAP, etc.)."""

    model_config = ConfigDict(frozen=True)

    lab_id: str
    name: str
    extracted_data: str | None = None


class MedicationEvidence(BaseModel):
    """Structured medication evidence for Clinical AI modules (Drug Intelligence, SOAP, etc.)."""

    model_config = ConfigDict(frozen=True)

    medication_id: str
    name: str
    amount: str = ""
    frequency: str = ""


class FileAnalysisEvidence(BaseModel):
    """File-analysis shaped evidence consumed by SOAP prompt rendering."""

    model_config = ConfigDict(frozen=True)

    lab_results: tuple[LabResultEvidence, ...] = ()
    medications: tuple[MedicationEvidenceItem, ...] = ()
    diagnoses: tuple[str, ...] = ()
    imaging_findings: str | None = None


class ClinicalContext(BaseModel):
    """
    Immutable clinical context assembled once per session.

    Source clinical aggregate shared by SOAP and future Clinical AI modules.
    ``timeline`` is the first *derived* clinical artifact attached additively
    for this sprint — do not grow this model into a long-term dump of derived
    AI outputs. See docs/adr/0001-clinical-artifacts-aggregate.md.
    """

    model_config = ConfigDict(frozen=True)

    session_id: int
    patient_id: int
    summary: MedicalSummary
    chat_history: tuple[ClinicalChatMessage, ...] = ()
    overview: MedicalOverview | None = None
    pmh_context: str | None = None
    pmh_answers: tuple[PMHAnswer, ...] = ()
    pmh_assertions: tuple[PMHAssertion, ...] = ()
    file_analyses: tuple[FileAnalysisEvidence, ...] = ()
    lab_evidence: tuple[LabEvidence, ...] = ()
    medication_evidence: tuple[MedicationEvidence, ...] = ()
    # First derived clinical artifact (additive; see ADR 0001).
    timeline: ClinicalTimeline | None = None
