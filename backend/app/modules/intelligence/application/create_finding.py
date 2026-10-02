"""CreateFinding use case."""

from __future__ import annotations

from app.modules.intelligence.application.commands import CreateFindingCommand
from app.modules.intelligence.application.repository import FindingRepositoryProtocol
from app.modules.intelligence.domain.models import ClinicalFinding


class CreateFindingUseCase:
    """Application use case: create and persist a ClinicalFinding."""

    def __init__(self, repository: FindingRepositoryProtocol) -> None:
        self._repository = repository

    async def execute(self, command: CreateFindingCommand) -> ClinicalFinding:
        finding = ClinicalFinding.create(
            session_id=command.session_id,
            category=command.category,
            severity=command.severity,
            title=command.title,
            source=command.source,
            summary=command.summary,
            confidence=command.confidence,
            evidence=command.evidence,
            source_id=command.source_id,
            context_hash=command.context_hash,
            finding_id=command.finding_id,
            created_at=command.created_at,
        )
        return await self._repository.save_finding(finding)
