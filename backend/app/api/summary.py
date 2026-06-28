import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.db.database import get_db
from app.models import Intake, Summary, User
from app.models import Session as SessionModel
from app.services.soap_task import trigger_soap_generation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])


async def _get_authorized_session(
    db: AsyncSession, session_id: int, current_user: User
) -> SessionModel:
    query = select(SessionModel).where(SessionModel.id == session_id)
    if current_user.role == "patient":
        query = query.where(SessionModel.patient_id == current_user.id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this session",
        )
    return session


@router.get("/{session_id}")
async def get_summary(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[dict]:
    session = await _get_authorized_session(db, session_id, current_user)

    sum_result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = sum_result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not found for session {session_id}",
        )

    intake_data = None
    intake_result = await db.execute(
        select(Intake).where(Intake.session_id == session_id)
    )
    intake = intake_result.scalar_one_or_none()
    if intake:
        from app.api.intake import _to_response

        intake_data = _to_response(intake).model_dump()

    assessment_data = None
    if summary.assessment:
        try:
            assessment_data = json.loads(summary.assessment)
        except json.JSONDecodeError:
            assessment_data = None

    soap_status = session.soap_status.value if session.soap_status else "pending"

    soap_citations = []
    if summary.soap_citations_json:
        try:
            soap_citations = json.loads(summary.soap_citations_json)
        except json.JSONDecodeError:
            soap_citations = []

    try:
        return {
            "id": summary.id,
            "session_id": summary.session_id,
            "soap_note": summary.soap_note,
            "soap_citations": soap_citations,
            "soap_status": soap_status,
            "soap_error_detail": session.soap_error_detail,
            "medical_data": {
                "chief_complaint": summary.chief_complaint,
                "history_present_illness": summary.history_present_illness,
                "past_medical_history": summary.past_medical_history,
                "medications": summary.medications,
                "allergies": summary.allergies,
            },
            "assessment_data": assessment_data,
            "intake": intake_data,
            "created_at": summary.created_at.isoformat() if summary.created_at else None,
        }
    except Exception as e:
        logger.error("Error formatting summary: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="خطا در واکشی اطلاعات خلاصه",
        )


@router.post("/{session_id}/retry-soap")
async def retry_soap_generation(
    session_id: int,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    session = await _get_authorized_session(db, session_id, current_user)

    sum_result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = sum_result.scalar_one_or_none()
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not found for session {session_id}",
        )

    session.soap_status = "generating"
    session.soap_error_detail = None
    await db.commit()

    trigger_soap_generation(background_tasks, session_id)
    return {"soap_status": "generating"}


@router.get("/session/{session_id}/exists")
async def check_summary_exists(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    await _get_authorized_session(db, session_id, current_user)

    sum_result = await db.execute(
        select(Summary).where(Summary.session_id == session_id)
    )
    summary = sum_result.scalar_one_or_none()
    return {"exists": summary is not None}
