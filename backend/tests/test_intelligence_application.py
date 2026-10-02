"""Clinical Intelligence application tests (InMemory repository; no Workspace)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.modules.intelligence.application.commands import (
    CreateFindingCommand,
    CreateRecommendationCommand,
    CreateRiskSignalCommand,
)
from app.modules.intelligence.application.create_finding import CreateFindingUseCase
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import ConfidenceScore, Evidence

NOW = datetime(2026, 8, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def repo() -> InMemoryFindingRepository:
    return InMemoryFindingRepository()


@pytest.fixture
def service(repo: InMemoryFindingRepository) -> FindingService:
    return FindingService(repo)


def _evidence() -> Evidence:
    return Evidence(
        source="labs",
        excerpt="Troponin elevated",
        confidence=ConfidenceScore(value=0.95),
    )


@pytest.mark.asyncio
async def test_create_finding_use_case_persists(repo: InMemoryFindingRepository) -> None:
    use_case = CreateFindingUseCase(repo)
    finding = await use_case.execute(
        CreateFindingCommand(
            session_id=10,
            category=FindingCategory.RED_FLAG,
            severity=FindingSeverity.CRITICAL,
            title="Elevated troponin",
            source=FindingSource.RULE_ENGINE,
            source_id="rule_execution_1",
            evidence=(_evidence(),),
            created_at=NOW,
        )
    )
    assert finding.finding_id
    assert finding.source_id == "rule_execution_1"
    stored = await repo.get_finding(finding.finding_id)
    assert stored is not None
    assert stored.title == "Elevated troponin"


@pytest.mark.asyncio
async def test_finding_service_list_for_session(service: FindingService) -> None:
    await service.create_finding(
        CreateFindingCommand(
            session_id=1,
            category=FindingCategory.OBSERVATION,
            severity=FindingSeverity.LOW,
            title="Mild fatigue",
            source=FindingSource.MANUAL,
            created_at=NOW,
        )
    )
    await service.create_finding(
        CreateFindingCommand(
            session_id=2,
            category=FindingCategory.OBSERVATION,
            severity=FindingSeverity.LOW,
            title="Other session",
            source=FindingSource.MANUAL,
            created_at=NOW,
        )
    )
    rows = await service.list_findings_for_session(1)
    assert len(rows) == 1
    assert rows[0].title == "Mild fatigue"


@pytest.mark.asyncio
async def test_create_risk_signal_requires_risk_key(service: FindingService) -> None:
    risk = await service.create_risk_signal(
        CreateRiskSignalCommand(
            session_id=5,
            risk_key="cardiovascular_risk",
            level=RiskLevel.HIGH,
            title="CV risk elevated",
            created_at=NOW,
        )
    )
    assert risk.risk_key == "cardiovascular_risk"
    listed = await service.list_risks_for_session(5)
    assert len(listed) == 1


@pytest.mark.asyncio
async def test_create_recommendation_defaults_active(service: FindingService) -> None:
    rec = await service.create_recommendation(
        CreateRecommendationCommand(
            session_id=5,
            kind=RecommendationKind.REVIEW,
            title="Review labs",
            created_at=NOW,
        )
    )
    assert rec.status is RecommendationStatus.ACTIVE

    superseded = await service.create_recommendation(
        CreateRecommendationCommand(
            session_id=5,
            kind=RecommendationKind.MONITOR,
            title="Old advice",
            status=RecommendationStatus.SUPERSEDED,
            created_at=NOW,
        )
    )
    assert superseded.status is RecommendationStatus.SUPERSEDED
    listed = await service.list_recommendations_for_session(5)
    assert len(listed) == 2
