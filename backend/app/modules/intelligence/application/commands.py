"""Commands for Clinical Intelligence write use cases."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import ConfidenceScore, Evidence


class CreateFindingCommand(BaseModel):
    """Input for creating a ClinicalFinding."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    category: FindingCategory
    severity: FindingSeverity
    title: str
    source: FindingSource
    summary: str = ""
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    source_id: str | None = None
    context_hash: str | None = None
    finding_id: str | None = None
    created_at: datetime | None = None


class CreateRiskSignalCommand(BaseModel):
    """Input for creating a RiskSignal."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    risk_key: str
    level: RiskLevel
    title: str
    finding_id: str | None = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    risk_id: str | None = None
    created_at: datetime | None = None


class CreateRecommendationCommand(BaseModel):
    """Input for creating a Recommendation."""

    model_config = ConfigDict(frozen=True)

    session_id: int
    kind: RecommendationKind
    title: str
    rationale: str = ""
    status: RecommendationStatus = RecommendationStatus.ACTIVE
    finding_id: str | None = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    recommendation_id: str | None = None
    created_at: datetime | None = None
