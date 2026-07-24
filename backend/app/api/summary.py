import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.session_access import get_authorized_session, is_doctor
from app.db.database import get_db
from app.models import File as FileModel
from app.models import Intake, Summary, User
from app.models import Session as SessionModel
from app.services.audit_service import record_audit
from app.services.medical_overview_service import (
    build_clinical_overview,
    load_medical_overview_from_intake,
    parse_legacy_soap,
)
from app.services.soap_task import trigger_soap_generation
from app.core.observability.context import get_correlation_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/summary", tags=["summary"])


async def _get_authorized_session(
    db: AsyncSession, session_id: int, current_user: User
) -> SessionModel:
    return await get_authorized_session(db, session_id, current_user, claim=True)


@router.get("/{session_id}")
async def get_summary(
    session_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[dict]:
    session = await _get_authorized_session(db, session_id, current_user)

    if is_doctor(current_user):
        client_ip = request.client.host if request.client else None
        await record_audit(
            db,
            action="view_session",
            user_id=current_user.id,
            resource_type="session",
            resource_id=session_id,
            ip_address=client_ip,
        )

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

    files_result = await db.execute(
        select(FileModel).where(FileModel.session_id == session_id)
    )
    files = list(files_result.scalars().all())
    overview = load_medical_overview_from_intake(intake)
    clinical_overview = build_clinical_overview(
        hpi=summary.history_present_illness,
        overview=overview,
        files=files,
    )

    try:
        return {
            "id": summary.id,
            "session_id": summary.session_id,
            "soap_note": summary.soap_note,
            "soap_citations": soap_citations,
            "soap_verification_status": summary.soap_verification_status,
            "soap_status": soap_status,
            "soap_error_detail": session.soap_error_detail,
            "legacy_soap": parse_legacy_soap(summary),
            "medical_data": {
                "chief_complaint": summary.chief_complaint,
                "history_present_illness": summary.history_present_illness,
                "past_medical_history": summary.past_medical_history,
                "medications": summary.medications,
                "allergies": summary.allergies,
            },
            "clinical_overview": clinical_overview.model_dump(),
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
    request: Request,
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

    client_ip = request.client.host if request.client else None
    await record_audit(
        db,
        action="retry_soap",
        user_id=current_user.id,
        resource_type="session",
        resource_id=session_id,
        ip_address=client_ip,
    )

    trigger_soap_generation(
        background_tasks,
        session_id,
        correlation_id=get_correlation_id(),
        entry="retry",
    )
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
