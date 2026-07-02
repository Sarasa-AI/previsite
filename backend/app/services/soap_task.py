import json
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_async_session
from app.models import Intake, Message, Session as DBSession, Summary
from app.schemas.medical import MedicalSummary
from app.services.medical_overview_service import (
    format_conditions_for_summary,
    load_medical_overview_from_intake,
)
from app.services.soap_generator import soap_generator

logger = logging.getLogger(__name__)


def _summary_text_field(value: str | None) -> list[str]:
    if not value or value.strip().lower() in {"نامشخص", "unknown", "n/a", ""}:
        return []
    return [value.strip()]


def _overview_allergies_list(allergies: str) -> list[str]:
    if not allergies or not allergies.strip():
        return []
    return [part.strip() for part in allergies.split("،") if part.strip()]


def _build_medical_summary_from_intake(intake: Intake) -> MedicalSummary | None:
    demographics = json.loads(intake.demographics_json) if intake.demographics_json else {}
    clinical = json.loads(intake.clinical_summary_json) if intake.clinical_summary_json else {}
    overview = load_medical_overview_from_intake(intake)

    if not clinical:
        return None

    past_medical_history = (
        _summary_text_field(
            format_conditions_for_summary(overview.chronic_conditions)
        )
        if overview
        else []
    )

    return MedicalSummary(
        chief_complaint=clinical.get("chief_complaint") or demographics.get("chief_complaint"),
        past_medical_history=past_medical_history,
        current_medications=list(overview.current_medications) if overview else [],
        allergies=_overview_allergies_list(overview.allergies) if overview else [],
        additional_notes=clinical.get("hpi_summary"),
        is_hpi_complete=True,
    )


def _build_medical_summary_from_chat(summary: Summary) -> MedicalSummary:
    return MedicalSummary(
        chief_complaint=summary.chief_complaint,
        past_medical_history=_summary_text_field(summary.past_medical_history),
        current_medications=_summary_text_field(summary.medications),
        allergies=_summary_text_field(summary.allergies),
        additional_notes=summary.history_present_illness,
        is_hpi_complete=getattr(summary, "is_hpi_complete", False) or False,
    )


def _archive_soap_to_legacy(summary: Summary, soap_note: str, citations: list, verification_status: str | None) -> None:
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


async def run_soap_generation(session_id: int) -> None:
    async with get_async_session() as db:
        try:
            result = await db.execute(
                select(DBSession).where(DBSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                return

            session.soap_status = "generating"
            session.soap_error_detail = None
            await db.commit()

            msg_result = await db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at)
            )
            db_messages = msg_result.scalars().all()
            chat_history: list[dict] = []
            if db_messages:
                chat_history = [{"role": m.role, "content": m.content} for m in db_messages]

            sum_result = await db.execute(
                select(Summary).where(Summary.session_id == session_id)
            )
            summary = sum_result.scalar_one_or_none()

            intake_result = await db.execute(
                select(Intake).where(Intake.session_id == session_id)
            )
            intake = intake_result.scalar_one_or_none()

            med_sum: MedicalSummary | None = None
            if intake and intake.clinical_summary_json:
                med_sum = _build_medical_summary_from_intake(intake)
            elif summary:
                med_sum = _build_medical_summary_from_chat(summary)

            if not med_sum:
                session.soap_status = "failed"
                session.soap_error_detail = "No clinical summary available for SOAP generation"
                await db.commit()
                return

            soap_note_result = await soap_generator.generate_soap_note(
                summary=med_sum,
                db=db,
                chat_history=chat_history,
                file_analyses=[],
                pmh_context=None,
                pmh_answers=None,
            )

            if soap_note_result.get("status") == "success":
                soap_note_content = soap_note_result.get("soap_note")
                citations = soap_note_result.get("citations") or []
                verification_status = soap_note_result.get("verification_status")
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
                logger.info("SOAP generation completed for session %s", session_id)
            else:
                session.soap_status = "failed"
                session.soap_error_detail = soap_note_result.get("message") or "SOAP generation failed"
                logger.warning(
                    "SOAP generation failed for session %s: %s",
                    session_id,
                    session.soap_error_detail,
                )

            await db.commit()
        except Exception as exc:
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


def trigger_soap_generation(background_tasks, session_id: int) -> None:
    background_tasks.add_task(run_soap_generation, session_id)
