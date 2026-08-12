"""Finding service — facade over repository and create use cases."""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.intelligence.application.commands import (
    CreateFindingCommand,
    CreateRecommendationCommand,
    CreateRiskSignalCommand,
)
from app.modules.intelligence.application.create_finding import CreateFindingUseCase
from app.modules.intelligence.application.repository import FindingRepositoryProtocol
from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    Recommendation,
    RiskSignal,
)


class FindingService:
    """Single seam between callers and Clinical Intelligence persistence."""

    def __init__(self, repository: FindingRepositoryProtocol) -> None:
        self._repository = repository
        self._create_finding = CreateFindingUseCase(repository)

    async def create_finding(self, command: CreateFindingCommand) -> ClinicalFinding:
        return await self._create_finding.execute(command)

    async def get_finding(self, finding_id: str) -> ClinicalFinding | None:
        return await self._repository.get_finding(finding_id)

    async def list_findings_for_session(
        self, session_id: int
    ) -> Sequence[ClinicalFinding]:
        return await self._repository.list_findings_for_session(session_id)

    async def create_risk_signal(
        self, command: CreateRiskSignalCommand
    ) -> RiskSignal:
        risk = RiskSignal.create(
            session_id=command.session_id,
            risk_key=command.risk_key,
            level=command.level,
            title=command.title,
            finding_id=command.finding_id,
            confidence=command.confidence,
            evidence=command.evidence,
            risk_id=command.risk_id,
            created_at=command.created_at,
        )
        return await self._repository.save_risk_signal(risk)

    async def list_risks_for_session(self, session_id: int) -> Sequence[RiskSignal]:
        return await self._repository.list_risks_for_session(session_id)

    async def create_recommendation(
        self, command: CreateRecommendationCommand
    ) -> Recommendation:
        recommendation = Recommendation.create(
            session_id=command.session_id,
            kind=command.kind,
            title=command.title,
            rationale=command.rationale,
            status=command.status,
            finding_id=command.finding_id,
            confidence=command.confidence,
            evidence=command.evidence,
            recommendation_id=command.recommendation_id,
            created_at=command.created_at,
        )
        return await self._repository.save_recommendation(recommendation)

    async def list_recommendations_for_session(
        self, session_id: int
    ) -> Sequence[Recommendation]:
        return await self._repository.list_recommendations_for_session(session_id)
