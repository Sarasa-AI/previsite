"""Clinical Intelligence Pipeline — connects document artifacts → inference → intelligence."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.inference.domain.models import InferenceRequest
from app.core.inference.infrastructure.composition import get_inference_pipeline
from app.core.observability.context import get_correlation_id
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage
from app.core.sentry import capture_categorized_error
from app.db.database import get_async_session
from app.models import ArtifactKind, DocumentArtifact, File as FileModel
from app.modules.intelligence.application.finding_service import FindingService
from app.modules.intelligence.application.orchestrator import ClinicalIntelligenceOrchestrator
from app.modules.intelligence.infrastructure.finding_repository import SqlAlchemyFindingRepository

if TYPE_CHECKING:
    from app.schemas.clinical_context import ClinicalContext


class ClinicalIntelligencePipeline:
    """
    Orchestrates the complete Clinical Intelligence pipeline:
    
    DocumentArtifacts (extraction) → InferencePipeline → InferenceResult
    → ClinicalIntelligenceOrchestrator → ClinicalFinding/RiskSignal/Recommendation
    
    This is the single production entry point for transforming uploaded documents
    into structured clinical intelligence.
    """

    def __init__(self) -> None:
        self._pipeline = None  # Lazy initialization

    def _get_pipeline(self):
        """Get or create the inference pipeline."""
        if self._pipeline is None:
            self._pipeline = get_inference_pipeline()
        return self._pipeline

    async def process_session_documents(
        self,
        session_id: int,
        product_key: str = "document_intelligence",
        correlation_id: str | None = None,
    ) -> dict:
        """
        Process all unprocessed extraction artifacts for a session through
        the inference and intelligence pipeline.

        Returns a summary of what was processed.
        """
        cid = correlation_id or get_correlation_id() or str(uuid.uuid4())

        async with get_async_session() as db:
            # Get all extraction artifacts for this session
            extraction_artifacts = await self._list_extraction_artifacts(db, session_id)

            if not extraction_artifacts:
                logger.info("No extraction artifacts found for session %s", session_id)
                return {
                    "session_id": session_id,
                    "processed": 0,
                    "message": "No extraction artifacts to process",
                }

            results = {
                "session_id": session_id,
                "total_artifacts": len(extraction_artifacts),
                "processed": 0,
                "inference_results": [],
                "intelligence_results": [],
                "errors": [],
            }

            for artifact in extraction_artifacts:
                try:
                    result = await self._process_single_artifact(
                        db=db,
                        session_id=session_id,
                        artifact=artifact,
                        product_key=product_key,
                        correlation_id=cid,
                    )
                    results["processed"] += 1
                    results["inference_results"].append(result.get("inference"))
                    results["intelligence_results"].append(result.get("intelligence"))
                except Exception as exc:
                    logger.exception(
                        "Failed to process artifact %s for session %s",
                        artifact.id,
                        session_id,
                    )
                    capture_categorized_error(
                        exc,
                        category="clinical_intelligence_pipeline",
                        context={"session_id": session_id, "artifact_id": artifact.id},
                    )
                    results["errors"].append({
                        "artifact_id": artifact.id,
                        "error": str(exc),
                    })

            await db.commit()
            logger.info(
                "Clinical intelligence pipeline completed for session %s: %d/%d processed",
                session_id,
                results["processed"],
                results["total_artifacts"],
            )
            return results

    async def _list_extraction_artifacts(
        self, db: AsyncSession, session_id: int
    ) -> list[DocumentArtifact]:
        """All extraction artifacts for a session, oldest first (stable ordering)."""
        result = await db.execute(
            select(DocumentArtifact)
            .where(
                DocumentArtifact.session_id == session_id,
                DocumentArtifact.kind == ArtifactKind.EXTRACTION,
            )
            .order_by(DocumentArtifact.file_id.asc(), DocumentArtifact.id.asc())
        )
        return list(result.scalars().all())

    async def _process_single_artifact(
        self,
        db: AsyncSession,
        session_id: int,
        artifact: DocumentArtifact,
        product_key: str,
        correlation_id: str,
    ) -> dict:
        """Process a single extraction artifact through inference and intelligence."""
        # Build context reference from extraction artifact
        context_reference = self._build_context_reference(artifact)

        # Create inference request
        request = InferenceRequest.create(
            session_id=session_id,
            product_key=product_key,
            context_reference=context_reference,
        )

        # Execute inference
        async with pipeline_stage(
            PipelineStage.INFERENCE_EXECUTION,
            module=PipelineModule.INFERENCE,
            session_id=session_id,
        ):
            pipeline = self._get_pipeline()
            inference_result = await pipeline.execute(request)

        # Transform inference result into clinical intelligence
        async with pipeline_stage(
            PipelineStage.INTELLIGENCE_ORCHESTRATION,
            module=PipelineModule.INTELLIGENCE,
            session_id=session_id,
        ):
            finding_repo = SqlAlchemyFindingRepository(db)
            finding_service = FindingService(finding_repo)
            orchestrator = ClinicalIntelligenceOrchestrator(finding_service)

            intelligence_result = await orchestrator.orchestrate(
                inference_result=inference_result,
                session_id=session_id,
            )

        return {
            "inference": {
                "execution_id": inference_result.execution_id,
                "status": inference_result.status.value,
                "findings_count": len(inference_result.findings),
                "duration": inference_result.duration,
            },
            "intelligence": {
                "execution_id": intelligence_result.execution_id,
                "findings_created": intelligence_result.processing_summary.created_findings,
                "risks_created": intelligence_result.processing_summary.created_risks,
                "recommendations_created": intelligence_result.processing_summary.created_recommendations,
                "validation_failures": intelligence_result.processing_summary.validation_failures,
            },
        }

    def _build_context_reference(self, artifact: DocumentArtifact) -> str:
        """
        Build a context reference from an extraction artifact.

        The context_reference is an opaque identifier that the inference adapter
        resolves to the actual clinical context. Here we embed the extraction
        payload directly as a JSON reference.
        """
        if artifact.payload_json:
            try:
                payload = json.loads(artifact.payload_json)
                # Create a deterministic reference from the extraction
                reference_data = {
                    "type": "extraction_artifact",
                    "artifact_id": artifact.id,
                    "file_id": artifact.file_id,
                    "session_id": artifact.session_id,
                    "extraction_summary": payload.get("values", []),
                }
                return json.dumps(reference_data, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass

        # Fallback: simple string reference
        return f"extraction:{artifact.session_id}:{artifact.file_id}:{artifact.id}"


# Singleton instance
clinical_intelligence_pipeline = ClinicalIntelligencePipeline()


async def run_clinical_intelligence_processing(
    session_id: int,
    product_key: str = "document_intelligence",
    correlation_id: str | None = None,
) -> None:
    """Run clinical intelligence processing for a session (inline, not background)."""
    await clinical_intelligence_pipeline.process_session_documents(
        session_id,
        product_key,
        correlation_id,
    )


def trigger_clinical_intelligence_processing(
    background_tasks,
    session_id: int,
    product_key: str = "document_intelligence",
    correlation_id: str | None = None,
) -> None:
    """Queue clinical intelligence processing on the request's background task set."""
    cid = correlation_id or get_correlation_id() or str(uuid.uuid4())
    background_tasks.add_task(
        run_clinical_intelligence_processing,
        session_id,
        product_key,
        cid,
    )


__all__ = [
    "ClinicalIntelligencePipeline",
    "clinical_intelligence_pipeline",
    "run_clinical_intelligence_processing",
    "trigger_clinical_intelligence_processing",
]
