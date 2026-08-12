"""One-way domain → DTO mappers for Clinical Intelligence."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    ConfidenceScore,
    Evidence,
    Recommendation,
    RiskSignal,
)
from app.modules.intelligence.interface.dto import (
    CONTRACT_VERSION,
    ClinicalFindingDTO,
    ClinicalFindingListResponse,
    ClinicalFindingResponse,
    ConfidenceScoreDTO,
    EvidenceDTO,
    RecommendationDTO,
    RiskSignalDTO,
)


def enum_to_wire(value: Enum | str) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def confidence_to_wire(score: ConfidenceScore) -> ConfidenceScoreDTO:
    if score.value == "unknown":
        return ConfidenceScoreDTO(value=None)
    return ConfidenceScoreDTO(value=float(score.value))


def format_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_evidence_dto(evidence: Evidence) -> EvidenceDTO:
    return EvidenceDTO(
        source=evidence.source,
        source_ref=evidence.source_ref,
        excerpt=evidence.excerpt,
        confidence=confidence_to_wire(evidence.confidence),
    )


def to_clinical_finding_dto(finding: ClinicalFinding) -> ClinicalFindingDTO:
    return ClinicalFindingDTO(
        finding_id=finding.finding_id,
        session_id=finding.session_id,
        category=enum_to_wire(finding.category),
        severity=enum_to_wire(finding.severity),
        title=finding.title,
        summary=finding.summary,
        confidence=confidence_to_wire(finding.confidence),
        evidence=[to_evidence_dto(e) for e in finding.evidence],
        source=enum_to_wire(finding.source),
        source_id=finding.source_id,
        context_hash=finding.context_hash,
        created_at=format_utc_z(finding.created_at),
        schema_version=finding.schema_version,
    )


def to_clinical_finding_response(finding: ClinicalFinding) -> ClinicalFindingResponse:
    return ClinicalFindingResponse(
        contract_version=CONTRACT_VERSION,
        finding=to_clinical_finding_dto(finding),
    )


def to_clinical_finding_list_response(
    session_id: int, findings: tuple[ClinicalFinding, ...] | list[ClinicalFinding]
) -> ClinicalFindingListResponse:
    return ClinicalFindingListResponse(
        contract_version=CONTRACT_VERSION,
        session_id=session_id,
        findings=[to_clinical_finding_dto(f) for f in findings],
    )


def to_risk_signal_dto(risk: RiskSignal) -> RiskSignalDTO:
    return RiskSignalDTO(
        risk_id=risk.risk_id,
        session_id=risk.session_id,
        risk_key=risk.risk_key,
        level=enum_to_wire(risk.level),
        title=risk.title,
        finding_id=risk.finding_id,
        confidence=confidence_to_wire(risk.confidence),
        evidence=[to_evidence_dto(e) for e in risk.evidence],
        created_at=format_utc_z(risk.created_at),
        schema_version=risk.schema_version,
    )


def to_recommendation_dto(recommendation: Recommendation) -> RecommendationDTO:
    return RecommendationDTO(
        recommendation_id=recommendation.recommendation_id,
        session_id=recommendation.session_id,
        kind=enum_to_wire(recommendation.kind),
        title=recommendation.title,
        rationale=recommendation.rationale,
        status=enum_to_wire(recommendation.status),
        finding_id=recommendation.finding_id,
        confidence=confidence_to_wire(recommendation.confidence),
        evidence=[to_evidence_dto(e) for e in recommendation.evidence],
        created_at=format_utc_z(recommendation.created_at),
        schema_version=recommendation.schema_version,
    )


# ---------------------------------------------------------------------------
# Orchestration result mappers
# ---------------------------------------------------------------------------


def to_processing_summary_dto(
    summary: "ProcessingSummary",
) -> "ProcessingSummaryDTO":
    from app.modules.intelligence.application.orchestrator import ProcessingSummary  # noqa: F401
    from app.modules.intelligence.interface.dto import ProcessingSummaryDTO

    return ProcessingSummaryDTO(
        execution_id=summary.execution_id,
        processed_count=summary.processed_count,
        created_findings=summary.created_findings,
        created_risks=summary.created_risks,
        created_recommendations=summary.created_recommendations,
        ignored_unknown=summary.ignored_unknown,
        validation_failures=summary.validation_failures,
    )


def to_clinical_intelligence_result_dto(
    result: "ClinicalIntelligenceResult",
) -> "ClinicalIntelligenceResultDTO":
    from app.modules.intelligence.application.orchestrator import ClinicalIntelligenceResult  # noqa: F401
    from app.modules.intelligence.interface.dto import ClinicalIntelligenceResultDTO

    return ClinicalIntelligenceResultDTO(
        execution_id=result.execution_id,
        findings=[to_clinical_finding_dto(f) for f in result.findings],
        risk_signals=[to_risk_signal_dto(r) for r in result.risk_signals],
        recommendations=[to_recommendation_dto(r) for r in result.recommendations],
        processing_summary=to_processing_summary_dto(result.processing_summary),
        processing_duration=result.processing_duration,
    )
