from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime

VerificationStatus = Literal["verified", "partially_verified", "unverified"]


class MedicalSummary(BaseModel):
    """Schema for medical information summary extracted from conversation"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "chief_complaint": "Severe headache for 3 days",
                "symptoms": ["headache", "nausea", "photophobia"],
                "symptom_duration": "3 days",
                "symptom_severity": "severe",
                "past_medical_history": ["hypertension", "migraine"],
                "current_medications": ["lisinopril 10mg daily"],
                "allergies": ["penicillin"],
                "smoking_status": "non-smoker",
                "alcohol_use": "occasional",
                "review_of_systems": {
                    "neurological": ["headache", "photophobia"],
                    "gastrointestinal": ["nausea"]
                },
                "additional_notes": "Patient reports stress at work",
                "confidence_score": 0.85
            }
        }
    )
    
    # Chief Complaint
    chief_complaint: Optional[str] = Field(None, description="Main reason for visit")
    
    # History of Present Illness
    symptoms: Optional[List[str]] = Field(default_factory=list, description="List of symptoms")
    symptom_duration: Optional[str] = Field(None, description="Duration of symptoms")
    symptom_severity: Optional[str] = Field(None, description="Severity: mild, moderate, severe")
    symptom_onset: Optional[str] = Field(None, description="Onset of symptoms")
    symptom_character: Optional[str] = Field(None, description="Character/quality of symptoms")
    symptom_location: Optional[str] = Field(None, description="Location of symptoms")
    symptom_aggravating_factors: Optional[List[str]] = Field(default_factory=list, description="Factors that aggravate symptoms")
    symptom_relieving_factors: Optional[List[str]] = Field(default_factory=list, description="Factors that relieve symptoms")
    symptom_radiation: Optional[str] = Field(None, description="Radiation of symptoms")
    symptom_timing: Optional[str] = Field(None, description="Timing of symptoms")
    
    # Past Medical History
    past_medical_history: Optional[List[str]] = Field(default_factory=list, description="Previous diagnoses")
    current_medications: Optional[List[str]] = Field(default_factory=list, description="Current medications")
    allergies: Optional[List[str]] = Field(default_factory=list, description="Known allergies")
    
    # Social History
    smoking_status: Optional[str] = Field(None, description="Smoking status")
    alcohol_use: Optional[str] = Field(None, description="Alcohol consumption")
    
    # Review of Systems
    review_of_systems: Optional[Dict[str, Any]] = Field(default_factory=dict, description="System-based symptoms")
    
    # Additional Information
    additional_notes: Optional[str] = Field(None, description="Any other relevant information")
    is_hpi_complete: bool = Field(False, description="Whether the History of Present Illness is clinically sufficient")
    
    # Metadata
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Extraction confidence")


class SoapNote(BaseModel):
    """Structured SOAP note with RAG evidence citations."""
    content: str = Field(..., description="Generated SOAP note markdown")
    citations: list[dict] = Field(default_factory=list, description="RAG evidence citations")
    verification_status: VerificationStatus = Field(
        default="verified",
        description="Aggregate citation verification outcome",
    )

