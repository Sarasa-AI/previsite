"""SQLAlchemy implementation of the Finding repository."""

from __future__ import annotations

import json
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    ConfidenceScore,
    Evidence,
    Recommendation,
    RiskSignal,
)
from app.modules.intelligence.infrastructure.models import (
    ClinicalFindingRecord,
    RecommendationRecord,
    RiskSignalRecord,
)


def _confidence_to_column(score: ConfidenceScore) -> float | None:
    if score.value == "unknown":
        return None
    return float(score.value)


def _confidence_from_column(value: float | None) -> ConfidenceScore:
    if value is None:
        return ConfidenceScore(value="unknown")
    return ConfidenceScore(value=float(value))


def _evidence_to_json(evidence: tuple[Evidence, ...]) -> str | None:
    if not evidence:
        return None
    payload = [
        {
            "source": e.source,
            "source_ref": e.source_ref,
            "excerpt": e.excerpt,
            "confidence": (
                None if e.confidence.value == "unknown" else float(e.confidence.value)
            ),
        }
        for e in evidence
    ]
    return json.dumps(payload)


def _evidence_from_json(raw: str | None) -> tuple[Evidence, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if not isinstance(parsed, list):
        return ()
    items: list[Evidence] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        conf_raw = item.get("confidence")
        conf = (
            ConfidenceScore(value="unknown")
            if conf_raw is None
            else ConfidenceScore(value=float(conf_raw))
        )
        try:
            items.append(
                Evidence(
                    source=str(item.get("source") or ""),
                    source_ref=item.get("source_ref"),
                    excerpt=str(item.get("excerpt") or ""),
                    confidence=conf,
                )
            )
        except Exception:
            continue
    return tuple(items)


class SqlAlchemyFindingRepository:
    """Clinical Intelligence persistence backed by SQLAlchemy tables."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_finding(self, finding: ClinicalFinding) -> ClinicalFinding:
        row = ClinicalFindingRecord(
            finding_id=finding.finding_id,
            session_id=finding.session_id,
            category=finding.category.value,
            severity=finding.severity.value,
            title=finding.title,
            summary=finding.summary,
            confidence=_confidence_to_column(finding.confidence),
            evidence_json=_evidence_to_json(finding.evidence),
            source=finding.source.value,
            source_id=finding.source_id,
            context_hash=finding.context_hash,
            schema_version=finding.schema_version,
            created_at=finding.created_at,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return self._finding_to_domain(row)

    async def get_finding(self, finding_id: str) -> ClinicalFinding | None:
        result = await self._db.execute(
            select(ClinicalFindingRecord).where(
                ClinicalFindingRecord.finding_id == finding_id
            )
        )
        row = result.scalar_one_or_none()
        return self._finding_to_domain(row) if row else None

    async def list_findings_for_session(
        self, session_id: int
    ) -> Sequence[ClinicalFinding]:
        result = await self._db.execute(
            select(ClinicalFindingRecord)
            .where(ClinicalFindingRecord.session_id == session_id)
            .order_by(ClinicalFindingRecord.created_at.asc(), ClinicalFindingRecord.id.asc())
        )
        rows = result.scalars().all()
        return tuple(self._finding_to_domain(row) for row in rows)

    async def save_risk_signal(self, risk: RiskSignal) -> RiskSignal:
        row = RiskSignalRecord(
            risk_id=risk.risk_id,
            session_id=risk.session_id,
            risk_key=risk.risk_key,
            level=risk.level.value,
            title=risk.title,
            finding_id=risk.finding_id,
            confidence=_confidence_to_column(risk.confidence),
            evidence_json=_evidence_to_json(risk.evidence),
            schema_version=risk.schema_version,
            created_at=risk.created_at,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return self._risk_to_domain(row)

    async def list_risks_for_session(self, session_id: int) -> Sequence[RiskSignal]:
        result = await self._db.execute(
            select(RiskSignalRecord)
            .where(RiskSignalRecord.session_id == session_id)
            .order_by(RiskSignalRecord.created_at.asc(), RiskSignalRecord.id.asc())
        )
        rows = result.scalars().all()
        return tuple(self._risk_to_domain(row) for row in rows)

    async def save_recommendation(
        self, recommendation: Recommendation
    ) -> Recommendation:
        row = RecommendationRecord(
            recommendation_id=recommendation.recommendation_id,
            session_id=recommendation.session_id,
            kind=recommendation.kind.value,
            title=recommendation.title,
            rationale=recommendation.rationale,
            status=recommendation.status.value,
            finding_id=recommendation.finding_id,
            confidence=_confidence_to_column(recommendation.confidence),
            evidence_json=_evidence_to_json(recommendation.evidence),
            schema_version=recommendation.schema_version,
            created_at=recommendation.created_at,
        )
        self._db.add(row)
        await self._db.commit()
        await self._db.refresh(row)
        return self._recommendation_to_domain(row)

    async def list_recommendations_for_session(
        self, session_id: int
    ) -> Sequence[Recommendation]:
        result = await self._db.execute(
            select(RecommendationRecord)
            .where(RecommendationRecord.session_id == session_id)
            .order_by(
                RecommendationRecord.created_at.asc(), RecommendationRecord.id.asc()
            )
        )
        rows = result.scalars().all()
        return tuple(self._recommendation_to_domain(row) for row in rows)

    @staticmethod
    def _finding_to_domain(row: ClinicalFindingRecord) -> ClinicalFinding:
        return ClinicalFinding(
            finding_id=row.finding_id,
            session_id=row.session_id,
            category=FindingCategory(row.category),
            severity=FindingSeverity(row.severity),
            title=row.title,
            summary=row.summary or "",
            confidence=_confidence_from_column(row.confidence),
            evidence=_evidence_from_json(row.evidence_json),
            source=FindingSource(row.source),
            source_id=row.source_id,
            context_hash=row.context_hash,
            created_at=row.created_at,
            schema_version=row.schema_version or "1.0.0",
        )

    @staticmethod
    def _risk_to_domain(row: RiskSignalRecord) -> RiskSignal:
        return RiskSignal(
            risk_id=row.risk_id,
            session_id=row.session_id,
            risk_key=row.risk_key,
            level=RiskLevel(row.level),
            title=row.title,
            finding_id=row.finding_id,
            confidence=_confidence_from_column(row.confidence),
            evidence=_evidence_from_json(row.evidence_json),
            created_at=row.created_at,
            schema_version=row.schema_version or "1.0.0",
        )

    @staticmethod
    def _recommendation_to_domain(row: RecommendationRecord) -> Recommendation:
        return Recommendation(
            recommendation_id=row.recommendation_id,
            session_id=row.session_id,
            kind=RecommendationKind(row.kind),
            title=row.title,
            rationale=row.rationale or "",
            status=RecommendationStatus(row.status),
            finding_id=row.finding_id,
            confidence=_confidence_from_column(row.confidence),
            evidence=_evidence_from_json(row.evidence_json),
            created_at=row.created_at,
            schema_version=row.schema_version or "1.0.0",
        )
