"""ClinicalIntelligenceOrchestrator — single entry point for transforming
InferenceResult objects into persistent Clinical Intelligence entities.

Architecture contract
---------------------
- This is the ONLY place where InferenceResult → Intelligence entity mapping
  is triggered.
- Runtime (core.inference) is imported here; Intelligence never imports Runtime
  in the reverse direction.
- Workspace packages are never imported.
"""

from __future__ import annotations

import logging
import time

from pydantic import BaseModel, ConfigDict

from app.core.inference.domain.models import InferenceResult
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.interpreter import (
    ArtifactInterpreter,
    InterpretedArtifacts,
)
from app.modules.intelligence.domain.models import (
    ClinicalFinding,
    Recommendation,
    RiskSignal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Immutable result models
# ---------------------------------------------------------------------------


class ProcessingSummary(BaseModel):
    """Diagnostic summary of a single orchestration run — immutable."""

    model_config = ConfigDict(frozen=True)

    execution_id: str
    processed_count: int
    created_findings: int
    created_risks: int
    created_recommendations: int
    ignored_unknown: int
    validation_failures: int


class ClinicalIntelligenceResult(BaseModel):
    """Immutable result returned by ClinicalIntelligenceOrchestrator.orchestrate.

    Contains no Workspace models.
    """

    model_config = ConfigDict(frozen=True)

    execution_id: str
    findings: tuple[ClinicalFinding, ...]
    risk_signals: tuple[RiskSignal, ...]
    recommendations: tuple[Recommendation, ...]
    processing_summary: ProcessingSummary
    processing_duration: float  # wall-clock seconds


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class ClinicalIntelligenceOrchestrator:
    """Transforms an :class:`~app.core.inference.domain.models.InferenceResult`
    into persisted Clinical Intelligence entities.

    This is the single authorised entry point for that transformation.

    Parameters
    ----------
    finding_service:
        Persistence facade — owns all repository interactions.
    interpreter:
        Artifact interpreter (injected for testability; a default instance is
        created when *None* is passed).
    """

    def __init__(
        self,
        finding_service: FindingService,
        interpreter: ArtifactInterpreter | None = None,
    ) -> None:
        self._service = finding_service
        self._interpreter = interpreter if interpreter is not None else ArtifactInterpreter()

    async def orchestrate(
        self,
        inference_result: InferenceResult,
        session_id: int,
    ) -> ClinicalIntelligenceResult:
        """Transform *inference_result* into Clinical Intelligence entities.

        The orchestration is fully traced: an outer *INTELLIGENCE_ORCHESTRATION*
        stage wraps an inner *INTELLIGENCE_INTERPRETATION* stage, then
        persistence.  All stages emit ClinicalPipelineEvent metrics.
        """
        wall_start = time.perf_counter()

        async with pipeline_stage(
            PipelineStage.INTELLIGENCE_ORCHESTRATION,
            module=PipelineModule.INTELLIGENCE,
            session_id=session_id,
        ):
            logger.debug(
                "Intelligence orchestration started — execution_id=%s session_id=%s",
                inference_result.execution_id,
                session_id,
            )

            # ---- Interpretation ----------------------------------------
            async with pipeline_stage(
                PipelineStage.INTELLIGENCE_INTERPRETATION,
                module=PipelineModule.INTELLIGENCE,
                session_id=session_id,
            ):
                interpreted: InterpretedArtifacts = self._interpreter.interpret(
                    session_id, inference_result.findings
                )

            # ---- Persistence -------------------------------------------
            findings: list[ClinicalFinding] = []
            for cmd in interpreted.findings:
                finding = await self._service.create_finding(cmd)
                findings.append(finding)

            risk_signals: list[RiskSignal] = []
            for cmd in interpreted.risk_signals:
                risk = await self._service.create_risk_signal(cmd)
                risk_signals.append(risk)

            recommendations: list[Recommendation] = []
            for cmd in interpreted.recommendations:
                rec = await self._service.create_recommendation(cmd)
                recommendations.append(rec)

            # ---- Result assembly ----------------------------------------
            processed_count = (
                len(interpreted.findings)
                + len(interpreted.risk_signals)
                + len(interpreted.recommendations)
                + interpreted.ignored_unknown
                + interpreted.validation_failures
            )

            summary = ProcessingSummary(
                execution_id=inference_result.execution_id,
                processed_count=processed_count,
                created_findings=len(findings),
                created_risks=len(risk_signals),
                created_recommendations=len(recommendations),
                ignored_unknown=interpreted.ignored_unknown,
                validation_failures=interpreted.validation_failures,
            )

            duration = time.perf_counter() - wall_start

            logger.debug(
                "Intelligence orchestration complete — execution_id=%s "
                "findings=%d risks=%d recommendations=%d ignored=%d failures=%d",
                inference_result.execution_id,
                summary.created_findings,
                summary.created_risks,
                summary.created_recommendations,
                summary.ignored_unknown,
                summary.validation_failures,
            )

            return ClinicalIntelligenceResult(
                execution_id=inference_result.execution_id,
                findings=tuple(findings),
                risk_signals=tuple(risk_signals),
                recommendations=tuple(recommendations),
                processing_summary=summary,
                processing_duration=duration,
            )
