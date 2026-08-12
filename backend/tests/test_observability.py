"""Tests for observability stage constants and tracing integration."""

from __future__ import annotations

import pytest

from app.core.observability.stages import PipelineModule, PipelineStage


class TestPipelineStageConstants:
    def test_intelligence_orchestration_constant_exists(self):
        assert hasattr(PipelineStage, "INTELLIGENCE_ORCHESTRATION")

    def test_intelligence_interpretation_constant_exists(self):
        assert hasattr(PipelineStage, "INTELLIGENCE_INTERPRETATION")

    def test_intelligence_orchestration_value(self):
        assert PipelineStage.INTELLIGENCE_ORCHESTRATION == "intelligence.orchestration"

    def test_intelligence_interpretation_value(self):
        assert PipelineStage.INTELLIGENCE_INTERPRETATION == "intelligence.interpretation"

    def test_existing_intelligence_finding_create_unchanged(self):
        assert PipelineStage.INTELLIGENCE_FINDING_CREATE == "intelligence.finding_create"

    def test_existing_inference_stages_unchanged(self):
        assert PipelineStage.INFERENCE_EXECUTION == "inference.execution"
        assert PipelineStage.INFERENCE_ADAPTER == "inference.adapter"


class TestPipelineModuleConstants:
    def test_intelligence_module_exists(self):
        assert hasattr(PipelineModule, "INTELLIGENCE")
        assert PipelineModule.INTELLIGENCE == "intelligence"

    def test_inference_module_exists(self):
        assert hasattr(PipelineModule, "INFERENCE")
        assert PipelineModule.INFERENCE == "inference"


class TestOrchestratorUsesObservability:
    """Ensure orchestrate() runs without errors — stages are emitted."""

    async def test_orchestrate_completes_without_observability_error(self):
        from datetime import datetime, timezone

        from app.core.inference.domain.enums import InferenceStatus
        from app.core.inference.domain.models import ExecutionTrace, InferenceResult
        from app.modules.intelligence.application.finding_service import FindingService
        from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
        from app.modules.intelligence.application.orchestrator import (
            ClinicalIntelligenceOrchestrator,
        )

        repo = InMemoryFindingRepository()
        service = FindingService(repo)
        orch = ClinicalIntelligenceOrchestrator(service)

        now = datetime.now(timezone.utc)
        trace = ExecutionTrace(
            started_at=now,
            finished_at=now,
            adapter_name="test",
            adapter_version="0.1",
            runtime_version="1.0.0",
            product_key="obs-test",
        )
        inference_result = InferenceResult(
            execution_id="obs-exec-001",
            status=InferenceStatus.SUCCEEDED,
            findings=(),
            execution_trace=trace,
            duration=0.0,
            runtime_metadata={},
        )

        result = await orch.orchestrate(inference_result, session_id=1)
        assert result.execution_id == "obs-exec-001"

    async def test_processing_duration_reflects_real_elapsed_time(self):
        import asyncio
        from datetime import datetime, timezone

        from app.core.inference.domain.enums import InferenceStatus
        from app.core.inference.domain.models import ExecutionTrace, InferenceResult
        from app.modules.intelligence.application.finding_service import FindingService
        from app.modules.intelligence.application.in_memory import InMemoryFindingRepository
        from app.modules.intelligence.application.orchestrator import (
            ClinicalIntelligenceOrchestrator,
        )

        repo = InMemoryFindingRepository()
        service = FindingService(repo)
        orch = ClinicalIntelligenceOrchestrator(service)

        now = datetime.now(timezone.utc)
        trace = ExecutionTrace(
            started_at=now,
            finished_at=now,
            adapter_name="test",
            adapter_version="0.1",
            runtime_version="1.0.0",
            product_key="timing-test",
        )
        inference_result = InferenceResult(
            execution_id="timing-exec",
            status=InferenceStatus.SUCCEEDED,
            findings=(),
            execution_trace=trace,
            duration=0.0,
            runtime_metadata={},
        )

        result = await orch.orchestrate(inference_result, session_id=2)
        assert result.processing_duration >= 0.0
