"""Document processing pipeline — the canonical upload → artifact path.

    File (storage)
      → run_document_ocr            → DocumentArtifact(kind='ocr')
      → extract_clinical_values     → DocumentArtifact(kind='extraction')
      → intake lab back-fill (only for condition-bound lab slots)
      → clinical intelligence pipeline (inference → intelligence)

Runs as a FastAPI background task after the upload request commits, so the HTTP
response stays fast while every uploaded document still reaches processing.

Idempotent: a file that already has artifacts is skipped, so retries and repeated
triggers cannot duplicate rows or double-charge OCR.

Failure policy is fail-closed and honest: when an engine is missing or the file is
unreadable the artifact is persisted with a ``failed`` / ``needs_review`` status and
an error detail. No clinical value is ever invented to fill the gap.
"""

from __future__ import annotations

import json

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.observability.context import bind, get_correlation_id, new_correlation_id
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.timing import pipeline_stage
from app.core.sentry import capture_categorized_error
from app.db.database import get_async_session
from app.models import ArtifactKind, ArtifactStatus, DocumentArtifact, Intake
from app.models import File as FileModel
from app.services.clinical_intelligence_pipeline import trigger_clinical_intelligence_processing
from app.services.document_extraction import ExtractionResult, extract_clinical_values
from app.services.document_ocr import (
    DocumentOcrError,
    DocumentOcrFailed,
    DocumentOcrUnavailable,
    OcrDocument,
    is_ocr_supported,
    run_document_ocr,
)
from app.services.medical_overview_service import (
    is_lab_bind_id,
    load_medical_overview_from_intake,
    update_lab_extracted_data,
)
from app.services.storage_service import storage_service


async def _existing_artifact_kinds(db: AsyncSession, file_id: int) -> set[str]:
    result = await db.execute(
        select(DocumentArtifact.kind).where(DocumentArtifact.file_id == file_id)
    )
    return {row[0] for row in result.all()}


async def get_latest_artifact(
    db: AsyncSession, file_id: int, kind: str
) -> DocumentArtifact | None:
    """Most recent artifact of ``kind`` for a file, or None."""
    result = await db.execute(
        select(DocumentArtifact)
        .where(DocumentArtifact.file_id == file_id, DocumentArtifact.kind == kind)
        .order_by(DocumentArtifact.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_extraction_artifacts(
    db: AsyncSession, session_id: int
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


def _ocr_status(document: OcrDocument) -> str:
    if not document.text.strip():
        return ArtifactStatus.EMPTY
    if document.needs_review:
        return ArtifactStatus.NEEDS_REVIEW
    return ArtifactStatus.SUCCEEDED


def _extraction_status(result: ExtractionResult) -> str:
    if result.is_empty:
        return ArtifactStatus.EMPTY
    if result.needs_review:
        return ArtifactStatus.NEEDS_REVIEW
    return ArtifactStatus.SUCCEEDED


async def _back_fill_intake_lab(
    db: AsyncSession,
    db_file: FileModel,
    result: ExtractionResult,
) -> bool:
    """Mirror the extraction digest onto a condition-bound lab slot.

    Only touches labs the patient explicitly bound this file to. Returns True when
    the intake row was updated.
    """
    condition_id = (db_file.condition_id or "").strip()
    if not condition_id or result.is_empty:
        return False

    intake_result = await db.execute(
        select(Intake).where(Intake.session_id == db_file.session_id)
    )
    intake = intake_result.scalar_one_or_none()
    if intake is None:
        return False

    overview = load_medical_overview_from_intake(intake)
    if not is_lab_bind_id(overview, condition_id):
        return False

    return update_lab_extracted_data(intake, condition_id, result.summary_text()) is not None


async def process_document_artifacts(
    session_id: int,
    file_id: int,
    correlation_id: str | None = None,
) -> None:
    """OCR + extract one uploaded document and persist both artifacts."""
    cid = correlation_id or get_correlation_id() or new_correlation_id()
    bind(correlation_id=cid, request_id=cid, session_id=session_id, module=PipelineModule.DOCUMENT)

    async with get_async_session() as db:
        try:
            file_result = await db.execute(
                select(FileModel).where(
                    FileModel.id == file_id, FileModel.session_id == session_id
                )
            )
            db_file = file_result.scalar_one_or_none()
            if not db_file:
                logger.warning("File not found for document processing: file_id=%s", file_id)
                return

            # Idempotency: skip if artifacts already exist for this file
            existing_kinds = await _existing_artifact_kinds(db, file_id)
            if ArtifactKind.OCR in existing_kinds and ArtifactKind.EXTRACTION in existing_kinds:
                logger.info("Artifacts already exist for file_id=%s, skipping", file_id)
                return

            # ---- OCR ----------------------------------------------------------
            async with pipeline_stage(
                PipelineStage.DOCUMENT_OCR,
                module=PipelineModule.DOCUMENT,
                session_id=session_id,
                file_id=file_id,
                recoverable_on_error=True,
            ) as ocr_stage:
                try:
                    file_bytes = await storage_service.download_file(db_file.s3_key)
                    document = run_document_ocr(file_bytes, db_file.content_type or "application/octet-stream")
                except DocumentOcrError as exc:
                    # Fail-closed: record the failure but do not invent OCR text
                    status = (
                        ArtifactStatus.NEEDS_REVIEW
                        if isinstance(exc, DocumentOcrUnavailable)
                        else ArtifactStatus.FAILED
                    )
                    await _persist_failure(
                        db,
                        session_id=session_id,
                        file_id=file_id,
                        kind=ArtifactKind.OCR,
                        error=f"{type(exc).__name__}: {exc}",
                        status=status,
                    )
                    logger.warning(
                        "Document OCR unavailable/failed file_id=%s status=%s error=%s",
                        file_id,
                        status,
                        exc,
                    )
                    return

                ocr_artifact = DocumentArtifact(
                    session_id=session_id,
                    file_id=file_id,
                    kind=ArtifactKind.OCR,
                    status=_ocr_status(document),
                    engine=document.engine,
                    engine_version=document.engine_version,
                    page_count=document.page_count,
                    raw_text=document.text or None,
                    confidence=document.confidence,
                )
                db.add(ocr_artifact)

            # ---- extraction ---------------------------------------------
            async with pipeline_stage(
                PipelineStage.DOCUMENT_EXTRACT,
                module=PipelineModule.DOCUMENT,
                session_id=session_id,
                recoverable_on_error=True,
            ) as extract_stage:
                extraction = extract_clinical_values(document)
                extract_stage.attrs["lab_count"] = len(extraction.values)

            extraction_artifact = DocumentArtifact(
                session_id=session_id,
                file_id=file_id,
                kind=ArtifactKind.EXTRACTION,
                status=_extraction_status(extraction),
                engine=extraction.to_payload()["method"],
                engine_version=extraction.to_payload()["method_version"],
                page_count=document.page_count,
                payload_json=json.dumps(extraction.to_payload(), ensure_ascii=False),
                confidence=document.confidence,
            )
            db.add(extraction_artifact)

            # ---- persist -------------------------------------------------
            async with pipeline_stage(
                PipelineStage.DOCUMENT_PERSIST,
                module=PipelineModule.DB,
                session_id=session_id,
                lab_count=len(extraction.values),
            ):
                await _back_fill_intake_lab(db, db_file, extraction)
                await db.commit()

            logger.info(
                "Document processed file_id=%s session_id=%s engine=%s pages=%s "
                "values=%s ocr_status=%s extraction_status=%s",
                file_id,
                session_id,
                document.engine,
                document.page_count,
                len(extraction.values),
                ocr_artifact.status,
                extraction_artifact.status,
            )
        except Exception as exc:  # noqa: BLE001 — background task must not crash the worker
            await db.rollback()
            logger.exception(
                "Document pipeline failed session_id=%s file_id=%s", session_id, file_id
            )
            capture_categorized_error(
                exc,
                category="document_pipeline",
                context={"session_id": session_id, "file_id": file_id},
            )


async def _persist_failure(
    db: AsyncSession,
    *,
    session_id: int,
    file_id: int,
    kind: str,
    error: str,
    status: str = ArtifactStatus.FAILED,
) -> None:
    """Record an explicit failure artifact so the gap is visible, not silent."""
    db.add(
        DocumentArtifact(
            session_id=session_id,
            file_id=file_id,
            kind=kind,
            status=status,
            engine="",
            engine_version="",
            error_detail=error[:2000],
        )
    )
    await db.commit()


def trigger_document_processing(
    background_tasks,
    session_id: int,
    file_id: int,
    correlation_id: str | None = None,
) -> None:
    """Queue document processing on the request's background task set."""
    cid = correlation_id or get_correlation_id() or new_correlation_id()
    background_tasks.add_task(process_document_artifacts, session_id, file_id, cid)

    # Also trigger clinical intelligence processing after document processing
    # This will run after the document artifacts are persisted
    trigger_clinical_intelligence_processing(
        background_tasks,
        session_id,
        product_key="document_intelligence",
        correlation_id=cid,
    )


__all__ = [
    "DocumentOcrFailed",
    "get_latest_artifact",
    "list_extraction_artifacts",
    "process_document_artifacts",
    "trigger_document_processing",
]
