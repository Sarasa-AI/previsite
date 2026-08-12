"""Immutable Clinical Intelligence domain models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)

ConfidenceValue = float | Literal["unknown"]

# Domain schema version (independent of wire CONTRACT_VERSION).
FINDING_SCHEMA_VERSION = "1.0.0"


class ConfidenceScore(BaseModel):
    """Bounded confidence value object."""

    model_config = ConfigDict(frozen=True)

    value: ConfidenceValue = "unknown"

    @field_validator("value")
    @classmethod
    def _validate_value(cls, value: ConfidenceValue) -> ConfidenceValue:
        if value == "unknown":
            return value
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0] or 'unknown'")
        return float(value)


class Evidence(BaseModel):
    """Source pointer supporting a finding, risk, or recommendation."""

    model_config = ConfigDict(frozen=True)

    source: str
    source_ref: str | None = None
    excerpt: str
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)

    @field_validator("source")
    @classmethod
    def _non_empty_source(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("source must be non-empty")
        return stripped

    @field_validator("excerpt")
    @classmethod
    def _non_empty_excerpt(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("excerpt must be non-empty")
        return stripped


class ClinicalFinding(BaseModel):
    """Immutable clinical finding — derived intelligence artifact."""

    model_config = ConfigDict(frozen=True)

    finding_id: str
    session_id: int
    category: FindingCategory
    severity: FindingSeverity
    title: str
    summary: str = ""
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    source: FindingSource
    source_id: str | None = None
    context_hash: str | None = None
    created_at: datetime
    schema_version: str = FINDING_SCHEMA_VERSION

    @field_validator("finding_id")
    @classmethod
    def _non_empty_finding_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("finding_id must be non-empty")
        return stripped

    @field_validator("title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must be non-empty")
        return stripped

    @field_validator("source_id")
    @classmethod
    def _normalize_source_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("session_id")
    @classmethod
    def _positive_session(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("session_id must be positive")
        return value

    @classmethod
    def create(
        cls,
        *,
        session_id: int,
        category: FindingCategory,
        severity: FindingSeverity,
        title: str,
        source: FindingSource,
        summary: str = "",
        confidence: ConfidenceScore | None = None,
        evidence: tuple[Evidence, ...] = (),
        source_id: str | None = None,
        context_hash: str | None = None,
        finding_id: str | None = None,
        created_at: datetime | None = None,
    ) -> ClinicalFinding:
        """Factory for a new immutable finding."""
        return cls(
            finding_id=finding_id or str(uuid.uuid4()),
            session_id=session_id,
            category=category,
            severity=severity,
            title=title,
            summary=summary,
            confidence=confidence or ConfidenceScore(),
            evidence=evidence,
            source=source,
            source_id=source_id,
            context_hash=context_hash,
            created_at=created_at or datetime.now(timezone.utc),
        )


class RiskSignal(BaseModel):
    """Immutable session-scoped risk signal with stable aggregation key."""

    model_config = ConfigDict(frozen=True)

    risk_id: str
    session_id: int
    risk_key: str
    level: RiskLevel
    title: str
    finding_id: str | None = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    created_at: datetime
    schema_version: str = FINDING_SCHEMA_VERSION

    @field_validator("risk_id")
    @classmethod
    def _non_empty_risk_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("risk_id must be non-empty")
        return stripped

    @field_validator("risk_key")
    @classmethod
    def _non_empty_risk_key(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("risk_key must be non-empty")
        return stripped

    @field_validator("title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must be non-empty")
        return stripped

    @field_validator("session_id")
    @classmethod
    def _positive_session(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("session_id must be positive")
        return value

    @classmethod
    def create(
        cls,
        *,
        session_id: int,
        risk_key: str,
        level: RiskLevel,
        title: str,
        finding_id: str | None = None,
        confidence: ConfidenceScore | None = None,
        evidence: tuple[Evidence, ...] = (),
        risk_id: str | None = None,
        created_at: datetime | None = None,
    ) -> RiskSignal:
        return cls(
            risk_id=risk_id or str(uuid.uuid4()),
            session_id=session_id,
            risk_key=risk_key,
            level=level,
            title=title,
            finding_id=finding_id,
            confidence=confidence or ConfidenceScore(),
            evidence=evidence,
            created_at=created_at or datetime.now(timezone.utc),
        )


class Recommendation(BaseModel):
    """Immutable recommendation — status modeled; no transition engine."""

    model_config = ConfigDict(frozen=True)

    recommendation_id: str
    session_id: int
    kind: RecommendationKind
    title: str
    rationale: str = ""
    status: RecommendationStatus = RecommendationStatus.ACTIVE
    finding_id: str | None = None
    confidence: ConfidenceScore = Field(default_factory=ConfidenceScore)
    evidence: tuple[Evidence, ...] = ()
    created_at: datetime
    schema_version: str = FINDING_SCHEMA_VERSION

    @field_validator("recommendation_id")
    @classmethod
    def _non_empty_recommendation_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("recommendation_id must be non-empty")
        return stripped

    @field_validator("title")
    @classmethod
    def _non_empty_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("title must be non-empty")
        return stripped

    @field_validator("session_id")
    @classmethod
    def _positive_session(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("session_id must be positive")
        return value

    @model_validator(mode="after")
    def _status_is_known(self) -> Recommendation:
        # Enum already constrains; keep explicit for domain readability.
        if self.status not in (
            RecommendationStatus.ACTIVE,
            RecommendationStatus.SUPERSEDED,
        ):
            raise ValueError("status must be ACTIVE or SUPERSEDED")
        return self

    @classmethod
    def create(
        cls,
        *,
        session_id: int,
        kind: RecommendationKind,
        title: str,
        rationale: str = "",
        status: RecommendationStatus = RecommendationStatus.ACTIVE,
        finding_id: str | None = None,
        confidence: ConfidenceScore | None = None,
        evidence: tuple[Evidence, ...] = (),
        recommendation_id: str | None = None,
        created_at: datetime | None = None,
    ) -> Recommendation:
        return cls(
            recommendation_id=recommendation_id or str(uuid.uuid4()),
            session_id=session_id,
            kind=kind,
            title=title,
            rationale=rationale,
            status=status,
            finding_id=finding_id,
            confidence=confidence or ConfidenceScore(),
            evidence=evidence,
            created_at=created_at or datetime.now(timezone.utc),
        )
