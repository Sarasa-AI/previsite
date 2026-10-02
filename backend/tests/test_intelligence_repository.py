"""Clinical Intelligence repository integration tests (real DB)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_password_hash
from app.models import Session as SessionModel
from app.models.user import User, UserRole
from app.modules.intelligence.application.commands import (
    CreateFindingCommand,
    CreateRecommendationCommand,
    CreateRiskSignalCommand,
)
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.domain.enums import (
    FindingCategory,
    FindingSeverity,
    FindingSource,
    RecommendationKind,
    RecommendationStatus,
    RiskLevel,
)
from app.modules.intelligence.domain.models import ConfidenceScore, Evidence
from app.modules.intelligence.infrastructure.finding_repository import (
    SqlAlchemyFindingRepository,
)
from app.modules.intelligence.interface.mappers import (
    to_clinical_finding_dto,
    to_recommendation_dto,
    to_risk_signal_dto,
)

NOW = datetime(2026, 8, 4, 14, 0, 0, tzinfo=timezone.utc)


async def _seed_session(db: AsyncSession) -> int:
    patient = User(
        email="intel-patient@test.com",
        full_name="intel_patient",
        hashed_password=get_password_hash("VeryStrongPassword123!"),
        role=UserRole.PATIENT,
        is_active=True,
    )
    doctor = User(
        email="intel-doctor@test.com",
        full_name="intel_doctor",
        hashed_password=get_password_hash("VeryStrongPassword123!"),
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db.add(patient)
    db.add(doctor)
    await db.flush()
    session = SessionModel(patient_id=patient.id, doctor_id=doctor.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session.id


@pytest.mark.asyncio
async def test_finding_round_trip_with_source_id(db: AsyncSession) -> None:
    session_id = await _seed_session(db)
    service = FindingService(SqlAlchemyFindingRepository(db))
    finding = await service.create_finding(
        CreateFindingCommand(
            session_id=session_id,
            category=FindingCategory.RED_FLAG,
            severity=FindingSeverity.CRITICAL,
            title="Chest pain with diaphoresis",
            source=FindingSource.RULE_ENGINE,
            source_id="rule_execution_42",
            confidence=ConfidenceScore(value=0.88),
            evidence=(
                Evidence(
                    source="intake",
                    excerpt="Crushing chest pain",
                    confidence=ConfidenceScore(value=0.9),
                ),
            ),
            created_at=NOW,
        )
    )
    loaded = await service.get_finding(finding.finding_id)
    assert loaded is not None
    assert loaded.source_id == "rule_execution_42"
    assert loaded.confidence.value == 0.88
    assert len(loaded.evidence) == 1
    assert loaded.evidence[0].excerpt == "Crushing chest pain"

    dto = to_clinical_finding_dto(loaded)
    assert dto.source_id == "rule_execution_42"
    assert dto.confidence.value == 0.88
    assert dto.category == "red_flag"


@pytest.mark.asyncio
async def test_risk_and_recommendation_persistence(db: AsyncSession) -> None:
    session_id = await _seed_session(db)
    service = FindingService(SqlAlchemyFindingRepository(db))

    risk = await service.create_risk_signal(
        CreateRiskSignalCommand(
            session_id=session_id,
            risk_key="cardiovascular_risk",
            level=RiskLevel.HIGH,
            title="Elevated cardiovascular risk",
            created_at=NOW,
        )
    )
    assert risk.risk_key == "cardiovascular_risk"
    risks = await service.list_risks_for_session(session_id)
    assert len(risks) == 1
    assert to_risk_signal_dto(risks[0]).risk_key == "cardiovascular_risk"

    rec = await service.create_recommendation(
        CreateRecommendationCommand(
            session_id=session_id,
            kind=RecommendationKind.REVIEW,
            title="Review ECG",
            status=RecommendationStatus.ACTIVE,
            confidence=ConfidenceScore(value="unknown"),
            created_at=NOW,
        )
    )
    assert rec.status is RecommendationStatus.ACTIVE
    recs = await service.list_recommendations_for_session(session_id)
    assert len(recs) == 1
    dto = to_recommendation_dto(recs[0])
    assert dto.status == "active"
    assert dto.confidence.value is None


@pytest.mark.asyncio
async def test_list_findings_ordered(db: AsyncSession) -> None:
    session_id = await _seed_session(db)
    service = FindingService(SqlAlchemyFindingRepository(db))
    t1 = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 8, 4, 11, 0, 0, tzinfo=timezone.utc)
    await service.create_finding(
        CreateFindingCommand(
            session_id=session_id,
            category=FindingCategory.OBSERVATION,
            severity=FindingSeverity.LOW,
            title="First",
            source=FindingSource.MANUAL,
            created_at=t1,
        )
    )
    await service.create_finding(
        CreateFindingCommand(
            session_id=session_id,
            category=FindingCategory.OBSERVATION,
            severity=FindingSeverity.LOW,
            title="Second",
            source=FindingSource.MANUAL,
            created_at=t2,
        )
    )
    rows = await service.list_findings_for_session(session_id)
    assert [r.title for r in rows] == ["First", "Second"]
