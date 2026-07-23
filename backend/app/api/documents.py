"""On-demand document OCR read API (Fail-Closed)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import doctor_may_access_session, get_authorized_session
from app.db.database import get_db
from app.models import File as FileModel
from app.models import Intake
from app.models import Session as SessionModel
from app.models import User
from app.models.user import UserRole
from app.services.medical_overview_service import load_medical_overview_from_intake

router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


class DocumentOcrResponse(BaseModel):
    ocr_text: str


def _not_found() -> HTTPException:
    """Generic 404 — does not reveal whether the file exists."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")


def _no_ocr_available() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="no_ocr_available",
    )


def _user_can_access_session(session: SessionModel, user: User) -> bool:
    if session.patient_id == user.id:
        return True
    if user.role == UserRole.DOCTOR or user.role == "doctor":
        return doctor_may_access_session(session, user)
    return False


@router.get("/{file_id}/ocr", response_model=DocumentOcrResponse)
async def get_document_ocr(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentOcrResponse:
    """Return stored lab OCR for a file, only after session auth.

    Resolution is strictly session-scoped: file → file.session_id intake →
    lab_results[] match on condition_id. Never search labs across sessions.
    """
    file_result = await db.execute(select(FileModel).where(FileModel.id == file_id))
    db_file = file_result.scalar_one_or_none()
    if not db_file:
        raise _not_found()

    session_result = await db.execute(
        select(SessionModel).where(SessionModel.id == db_file.session_id)
    )
    session = session_result.scalar_one_or_none()
    if not session or not _user_can_access_session(session, current_user):
        raise _not_found()

    # Claim-on-open for doctors viewing OCR on an unassigned session.
    if session.patient_id != current_user.id:
        try:
            await get_authorized_session(
                db, session.id, current_user, claim=True, not_found_as_403=False
            )
        except HTTPException:
            raise _not_found()

    condition_id = (db_file.condition_id or "").strip()
    if not condition_id:
        raise _no_ocr_available()

    intake_result = await db.execute(
        select(Intake).where(Intake.session_id == db_file.session_id)
    )
    intake = intake_result.scalar_one_or_none()
    overview = load_medical_overview_from_intake(intake)
    if not overview:
        raise _no_ocr_available()

    matched_lab = next(
        (lab for lab in overview.lab_results if lab.id == condition_id),
        None,
    )
    ocr_text = (matched_lab.extracted_data or "").strip() if matched_lab else ""
    if not ocr_text:
        raise _no_ocr_available()

    return DocumentOcrResponse(ocr_text=ocr_text)
