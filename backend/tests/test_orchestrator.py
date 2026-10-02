"""Tests for ClinicalIntelligenceOrchestrator."""

from __future__ import annotations

import pytest

from app.core.inference.domain.enums import InferenceStatus
from app.core.inference.domain.models import (
    ExecutionTrace,
    InferenceFinding,
    InferenceResult,
)
from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.interpreter import ArtifactInterpreter
from app.modules.intelligence.application.orchestrator import (
    ClinicalIntelligenceOrchestrator,
    ClinicalIntelligenceResult,
    ProcessingSummary,
)
from app.modules.intelligence.domain.enums import FindingSource
from datetime import datetime, timezone


SESSION_ID = 5


def _trace() -> ExecutionTrace:
    now = datetime.now(timezone.utc)
    return ExecutionTrace(
        started_at=now,
        finished_at=now,
        adapter_name="fake",
        adapter_version="1.0",
        runtime_version="1.0.0",
        product_key="test-product",
    )


def _result(
    execution_id: str = "exec-abc-123",
    findings: tuple[InferenceFinding, ...] = (),
) -> InferenceResult:
    return InferenceResult(
        execution_id=execution_id,
        status=InferenceStatus.SUCCEEDED,
        findings=findings,
        execution_trace=_trace(),
        duration=0.1,
        runtime_metadata={},
    )


def _finding(
    artifact_type: str = "clinical_finding",
    title: str = "Test Finding",
    key: str = "k1",
    attributes: dict | None = None,
) -> InferenceFinding:
    return InferenceFinding(
        artifact_type=artifact_type,
        finding_key=key,
        title=title,
        summary="Summary of finding",
        confidence=0.85,
        attributes=attributes or {},
    )


@pytest.fixture
def repo():
    r = InMemoryFindingRepository()
    yield r
    r.clear()


@pytest.fixture
def service(repo):
    return FindingService(repo)


@pytest.fixture
def orchestrator(service):
    return ClinicalIntelligenceOrchestrator(service)


class TestOrchestratorHappyPath:
    async def test_returns_clinical_intelligence_result(self, orchestrator):
        result = await orchestrator.orchestrate(_result(), SESSION_ID)
        assert isinstance(result, ClinicalIntelligenceResult)

    async def test_execution_id_matches_inference_result(self, orchestrator):
        result = await orchestrator.orchestrate(_result(execution_id="xid-001"), SESSION_ID)
        assert result.execution_id == "xid-001"

    async def test_processing_duration_is_positive(self, orchestrator):
        result = await orchestrator.orchestrate(_result(), SESSION_ID)
        assert result.processing_duration >= 0.0

    async def test_empty_findings_produces_empty_result(self, orchestrator):
        result = await orchestrator.orchestrate(_result(findings=()), SESSION_ID)
        assert result.findings == ()
        assert result.risk_signals == ()
        assert result.recommendations == ()

    async def test_clinical_finding_persisted(self, orchestrator, repo):
        artifact = _finding(artifact_type="clinical_finding", key="cf-1", title="Hypertension")
        result = await orchestrator.orchestrate(_result(findings=(artifact,)), SESSION_ID)

        assert len(result.findings) == 1
        assert result.findings[0].title == "Hypertension"
        assert result.findings[0].session_id == SESSION_ID
        assert result.findings[0].source == FindingSource.AI_RUNTIME

        stored = await repo.list_findings_for_session(SESSION_ID)
        assert len(stored) == 1
        assert stored[0].title == "Hypertension"

    async def test_risk_signal_persisted(self, orchestrator, repo):
        artifact = _finding(artifact_type="risk_signal", key="rs-1", title="Cardiac Risk")
        result = await orchestrator.orchestrate(_result(findings=(artifact,)), SESSION_ID)

        assert len(result.risk_signals) == 1
        assert result.risk_signals[0].title == "Cardiac Risk"

        stored = await repo.list_risks_for_session(SESSION_ID)
        assert len(stored) == 1

    async def test_recommendation_persisted(self, orchestrator, repo):
        artifact = _finding(artifact_type="recommendation", key="rec-1", title="Follow-up ECG")
        result = await orchestrator.orchestrate(_result(findings=(artifact,)), SESSION_ID)

        assert len(result.recommendations) == 1
        assert result.recommendations[0].title == "Follow-up ECG"

        stored = await repo.list_recommendations_for_session(SESSION_ID)
        assert len(stored) == 1

    async def test_mixed_artifact_types(self, orchestrator, repo):
        artifacts = (
            _finding(artifact_type="clinical_finding", key="f1", title="Finding"),
            _finding(artifact_type="risk_signal", key="r1", title="Risk"),
            _finding(artifact_type="recommendation", key="rc1", title="Rec"),
        )
        result = await orchestrator.orchestrate(_result(findings=artifacts), SESSION_ID)

        assert len(result.findings) == 1
        assert len(result.risk_signals) == 1
        assert len(result.recommendations) == 1


class TestOrchestratorProcessingSummary:
    async def test_summary_execution_id_matches(self, orchestrator):
        result = await orchestrator.orchestrate(_result(execution_id="eid-sum"), SESSION_ID)
        assert result.processing_summary.execution_id == "eid-sum"

    async def test_summary_counts_clinical_findings(self, orchestrator):
        artifacts = (
            _finding(key="f1", title="Finding 1"),
            _finding(key="f2", title="Finding 2"),
        )
        result = await orchestrator.orchestrate(_result(findings=artifacts), SESSION_ID)
        assert result.processing_summary.created_findings == 2
        assert result.processing_summary.processed_count == 2

    async def test_summary_counts_unknown_ignored(self, orchestrator):
        artifacts = (
            _finding(artifact_type="clinical_finding", key="f1", title="Known"),
            _finding(artifact_type="future_type", key="u1", title="Unknown"),
        )
        result = await orchestrator.orchestrate(_result(findings=artifacts), SESSION_ID)
        assert result.processing_summary.ignored_unknown == 1
        assert result.processing_summary.created_findings == 1
        assert result.processing_summary.processed_count == 2

    async def test_summary_all_zeros_for_empty(self, orchestrator):
        result = await orchestrator.orchestrate(_result(findings=()), SESSION_ID)
        s = result.processing_summary
        assert s.processed_count == 0
        assert s.created_findings == 0
        assert s.created_risks == 0
        assert s.created_recommendations == 0
        assert s.ignored_unknown == 0
        assert s.validation_failures == 0

    async def test_summary_is_frozen(self, orchestrator):
        from pydantic import ValidationError
        result = await orchestrator.orchestrate(_result(), SESSION_ID)
        with pytest.raises((ValidationError, TypeError)):
            result.processing_summary.created_findings = 99  # type: ignore[misc]


class TestOrchestratorResultImmutability:
    async def test_result_is_frozen(self, orchestrator):
        from pydantic import ValidationError
        result = await orchestrator.orchestrate(_result(), SESSION_ID)
        with pytest.raises((ValidationError, TypeError)):
            result.execution_id = "changed"  # type: ignore[misc]

    async def test_findings_is_tuple(self, orchestrator):
        result = await orchestrator.orchestrate(_result(), SESSION_ID)
        assert isinstance(result.findings, tuple)
        assert isinstance(result.risk_signals, tuple)
        assert isinstance(result.recommendations, tuple)


class TestOrchestratorDefaultInterpreter:
    async def test_default_interpreter_created_when_none_passed(self, service):
        orch = ClinicalIntelligenceOrchestrator(service, interpreter=None)
        result = await orch.orchestrate(_result(), SESSION_ID)
        assert isinstance(result, ClinicalIntelligenceResult)
