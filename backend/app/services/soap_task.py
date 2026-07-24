import json
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.observability.context import bind, get_correlation_id, new_correlation_id
from app.core.observability.errors import emit_pipeline_failure
from app.core.observability.metrics import (
    inc_soap_failure,
    inc_soap_success,
    observe_pipeline_latency,
)
from app.core.observability.stages import PipelineModule, PipelineStage
from app.core.observability.telemetry import (
    build_pipeline_event,
    emit_pipeline_event,
)
from app.core.observability.timing import pipeline_stage
from app.db.database import get_async_session
from app.models import Session as DBSession, Summary
from app.services.clinical_context_builder import clinical_context_builder
from app.services.soap_generator import soap_generator

logger = logging.getLogger(__name__)


def _archive_soap_to_legacy(
    summary: Summary,
    soap_note: str,
    citations: list,
    verification_status: str | None,
) -> None:
    payload = {
        "soap_note": soap_note,
        "soap_citations": citations,
        "soap_verification_status": verification_status,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
    summary.legacy_soap_json = json.dumps(payload, ensure_ascii=False)
    summary.soap_note = soap_note
    summary.soap_citations_json = json.dumps(citations, ensure_ascii=False)
    summary.soap_verification_status = verification_status


def _context_counts(clinical_context) -> dict:
    return {
        "lab_count": len(clinical_context.lab_evidence or ()),
        "medication_count": len(clinical_context.medication_evidence or ()),
        "pmh_count": len(clinical_context.pmh_assertions or ()),
        "evidence_count": None,
        "session_id": clinical_context.session_id,
        "patient_id": clinical_context.patient_id,
    }


async def run_soap_generation(
    session_id: int,
    correlation_id: str | None = None,
    entry: str = "unknown",
) -> None:
    cid = correlation_id or get_correlation_id() or new_correlation_id()
    bind(correlation_id=cid, request_id=cid, session_id=session_id)
    pipeline_start = time.perf_counter()

    async with get_async_session() as db:
        try:
            result = await db.execute(
                select(DBSession).where(DBSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return

            bind(patient_id=session.patient_id)
            session.soap_status = "generating"
            session.soap_error_detail = None
            await db.commit()

            sum_result = await db.execute(
                select(Summary).where(Summary.session_id == session_id)
            )
            summary = sum_result.scalar_one_or_none()

            try:
                async with pipeline_stage(
                    PipelineStage.CLINICAL_CONTEXT_BUILD,
                    module=PipelineModule.CLINICAL_CONTEXT,
                    session_id=session_id,
                    patient_id=session.patient_id,
                ):
                    clinical_context = await clinical_context_builder.build(db, session_id)
            except ValueError as exc:
                session.soap_status = "failed"
                session.soap_error_detail = str(exc)
                await db.commit()
                inc_soap_failure(type(exc).__name__)
                observe_pipeline_latency(
                    entry, int((time.perf_counter() - pipeline_start) * 1000)
                )
                return

            counts = _context_counts(clinical_context)
            soap_note_result = await soap_generator.generate_soap_note(
                clinical_context=clinical_context,
                db=db,
            )

            if soap_note_result.get("status") == "success":
                soap_note_content = soap_note_result.get("soap_note")
                citations = soap_note_result.get("citations") or []
                verification_status = soap_note_result.get("verification_status")
                async with pipeline_stage(
                    PipelineStage.DB_PERSIST_SOAP,
                    module=PipelineModule.DB,
                    session_id=session_id,
                    patient_id=session.patient_id,
                    evidence_count=len(citations),
                    conflict_count=soap_note_result.get("conflict_count"),
                    **{
                        k: counts[k]
                        for k in ("lab_count", "medication_count", "pmh_count")
                    },
                ):
                    if summary:
                        _archive_soap_to_legacy(
                            summary,
                            soap_note_content,
                            citations,
                            verification_status,
                        )
                    else:
                        summary = Summary(session_id=session_id)
                        _archive_soap_to_legacy(
                            summary,
                            soap_note_content,
                            citations,
                            verification_status,
                        )
                        db.add(summary)
                    session.soap_status = "ready"
                    session.soap_error_detail = None
                    await db.commit()
                inc_soap_success()
                logger.info("SOAP generation completed for session %s", session_id)
            else:
                session.soap_status = "failed"
                session.soap_error_detail = (
                    soap_note_result.get("message") or "SOAP generation failed"
                )
                await db.commit()
                error_type = soap_note_result.get("error_type") or "SoapGenerationError"
                emit_pipeline_event(
                    build_pipeline_event(
                        module=PipelineModule.SOAP,
                        pipeline_stage=PipelineStage.SOAP_GENERATE,
                        latency_ms=soap_note_result.get("latency_ms") or 0,
                        status="failure",
                        session_id=session_id,
                        patient_id=session.patient_id,
                        error_type=error_type,
                        recoverable=False,
                        retryable=True,
                    )
                )
                inc_soap_failure(error_type)
                logger.warning(
                    "SOAP generation failed for session %s: %s",
                    session_id,
                    session.soap_error_detail,
                )

            observe_pipeline_latency(
                entry, int((time.perf_counter() - pipeline_start) * 1000)
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - pipeline_start) * 1000)
            emit_pipeline_failure(
                module=PipelineModule.SOAP,
                stage=PipelineStage.SOAP_PIPELINE,
                exc=exc,
                duration_ms=duration_ms,
                recoverable=False,
                retryable=True,
                session_id=session_id,
            )
            inc_soap_failure(type(exc).__name__)
            observe_pipeline_latency(entry, duration_ms)
            logger.exception("SOAP generation error for session %s", session_id)
            try:
                result = await db.execute(
                    select(DBSession).where(DBSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.soap_status = "failed"
                    session.soap_error_detail = str(exc)
                    await db.commit()
            except Exception:
                await db.rollback()


def trigger_soap_generation(
    background_tasks,
    session_id: int,
    correlation_id: str | None = None,
    entry: str = "unknown",
) -> None:
    cid = correlation_id or get_correlation_id() or new_correlation_id()
    background_tasks.add_task(run_soap_generation, session_id, cid, entry)
