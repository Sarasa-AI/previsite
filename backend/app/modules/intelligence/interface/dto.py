"""Wire DTOs for Clinical Intelligence — no domain enums, no business behavior."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# Wire contract version (independent of FINDING_SCHEMA_VERSION).
CONTRACT_VERSION = "1.0.0"


class ConfidenceScoreDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: float | None = None


class EvidenceDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    source_ref: str | None = None
    excerpt: str
    confidence: ConfidenceScoreDTO = Field(default_factory=ConfidenceScoreDTO)


class ClinicalFindingDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str
    session_id: int
    category: str
    severity: str
    title: str
    summary: str = ""
    confidence: ConfidenceScoreDTO = Field(default_factory=ConfidenceScoreDTO)
    evidence: list[EvidenceDTO] = Field(default_factory=list)
    source: str
    source_id: str | None = None
    context_hash: str | None = None
    created_at: str
    schema_version: str


class RiskSignalDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    risk_id: str
    session_id: int
    risk_key: str
    level: str
    title: str
    finding_id: str | None = None
    confidence: ConfidenceScoreDTO = Field(default_factory=ConfidenceScoreDTO)
    evidence: list[EvidenceDTO] = Field(default_factory=list)
    created_at: str
    schema_version: str


class RecommendationDTO(BaseModel):
    model_config = ConfigDict(frozen=True)

    recommendation_id: str
    session_id: int
    kind: str
    title: str
    rationale: str = ""
    status: str
    finding_id: str | None = None
    confidence: ConfidenceScoreDTO = Field(default_factory=ConfidenceScoreDTO)
    evidence: list[EvidenceDTO] = Field(default_factory=list)
    created_at: str
    schema_version: str


class ClinicalFindingResponse(BaseModel):
    """Versioned envelope for a single finding."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = CONTRACT_VERSION
    finding: ClinicalFindingDTO


class ClinicalFindingListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    contract_version: str = CONTRACT_VERSION
    session_id: int
    findings: list[ClinicalFindingDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Orchestration result DTOs
# ---------------------------------------------------------------------------


class ProcessingSummaryDTO(BaseModel):
    """Wire representation of a ProcessingSummary — diagnostics only."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    processed_count: int
    created_findings: int
    created_risks: int
    created_recommendations: int
    ignored_unknown: int
    validation_failures: int


class ClinicalIntelligenceResultDTO(BaseModel):
    """Versioned wire envelope for a complete orchestration result."""

    model_config = ConfigDict(frozen=True)

    contract_version: str = CONTRACT_VERSION
    execution_id: str
    findings: list[ClinicalFindingDTO] = Field(default_factory=list)
    risk_signals: list[RiskSignalDTO] = Field(default_factory=list)
    recommendations: list[RecommendationDTO] = Field(default_factory=list)
    processing_summary: ProcessingSummaryDTO
    processing_duration: float
